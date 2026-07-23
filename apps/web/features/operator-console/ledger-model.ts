/**
 * Pure hypothesis-ledger transform: operator-pinned hypotheses + agent (ORACLE) hypotheses +
 * bias-guard findings -> ordered ledger cards with CHALLENGED badges.
 *
 * Kept React-free and total so the challenge-matching and no-change-collapse rules are
 * unit-testable in isolation. A bias-guard finding is an autonomous ORACLE task ("Bias guard:
 * …") that re-examined a leading hypothesis against new evidence; when it contradicts a
 * hypothesis we badge that card, and routine "NO_CHANGE" checks collapse to a count.
 */

import type { AgentSessionDetailV1, HypothesisV1 } from '@aegis/contracts-ts';

export interface LedgerCard {
  id: string;
  statement: string;
  confidence: number | null;
  origin: 'operator' | 'agent';
  evidenceIds: string[];
  challenged: boolean;
  challengeRationale: string | null;
}

export interface HypothesisLedger {
  cards: LedgerCard[];
  collapsedNoChangeCount: number;
}

interface BiasGuardFinding {
  isNoChange: boolean;
  rationale: string;
  contradictedEvidenceIds: Set<string>;
  contradictedStatements: string[];
}

const NO_CHANGE_MARKERS = ['no_change', 'nochange', 'no change'];

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value : null;
}

function collectStrings(value: unknown): string[] {
  if (typeof value === 'string') {
    return value.trim().length > 0 ? [value] : [];
  }
  if (Array.isArray(value)) {
    return value.flatMap(collectStrings);
  }
  return [];
}

function normalize(statement: string): string {
  return statement.toLowerCase().replace(/\s+/g, ' ').trim();
}

function isBiasGuardTaskInstruction(instructions: string | null | undefined): boolean {
  if (!instructions) {
    return false;
  }
  const text = instructions.toLowerCase();
  return text.includes('bias guard') || text.includes('contradict');
}

/**
 * Pull contradiction signals out of a bias-guard artifact payload, digging into the common
 * ORACLE output shapes (top-level markers, and per-`hypotheses`/`claims` entries). Defensive
 * against a still-settling payload — absence of a signal means "nothing contradicted".
 */
function readFinding(payload: Record<string, unknown>): BiasGuardFinding {
  const evidence = new Set<string>();
  const statements: string[] = [];

  const pushEvidence = (value: unknown) => {
    for (const id of collectStrings(value)) {
      evidence.add(id);
    }
  };

  pushEvidence(payload.contradictingEvidenceIds);
  for (const statement of collectStrings(payload.contradicts)) {
    statements.push(statement);
  }

  for (const key of ['hypotheses', 'claims', 'contradictionLinks']) {
    const entries = payload[key];
    if (!Array.isArray(entries)) {
      continue;
    }
    for (const entry of entries) {
      if (typeof entry !== 'object' || entry === null) {
        continue;
      }
      const record = entry as Record<string, unknown>;
      pushEvidence(record.contradictingEvidenceIds);
      const statement = asString(record.statement) ?? asString(record.text);
      const hasContradiction =
        (Array.isArray(record.contradictingEvidenceIds) &&
          record.contradictingEvidenceIds.length > 0) ||
        record.contradicts === true ||
        record.isContradiction === true;
      if (statement && hasContradiction) {
        statements.push(statement);
      }
    }
  }

  const rationale = asString(payload.rationale) ?? asString(payload.executiveSummary) ?? '';
  const rationaleLower = rationale.toLowerCase();
  const hasSignal = evidence.size > 0 || statements.length > 0;
  const markedNoChange = NO_CHANGE_MARKERS.some((marker) => rationaleLower.includes(marker));

  return {
    isNoChange: !hasSignal && (markedNoChange || rationale.length === 0),
    rationale,
    contradictedEvidenceIds: evidence,
    contradictedStatements: statements,
  };
}

function extractBiasGuardFindings(sessions: AgentSessionDetailV1[]): BiasGuardFinding[] {
  const findings: BiasGuardFinding[] = [];
  for (const detail of sessions) {
    if (detail.session.role !== 'ORACLE') {
      continue;
    }
    const biasTaskIds = new Set(
      detail.tasks
        .filter(
          (task) => task.initiator === 'autonomy' && isBiasGuardTaskInstruction(task.instructions),
        )
        .map((task) => task.id),
    );
    if (biasTaskIds.size === 0) {
      continue;
    }
    for (const artifact of detail.artifacts) {
      if (!biasTaskIds.has(artifact.taskId)) {
        continue;
      }
      findings.push(readFinding(artifact.payload));
    }
  }
  return findings;
}

function findChallenge(
  card: { statement: string; evidenceIds: string[] },
  findings: BiasGuardFinding[],
): BiasGuardFinding | null {
  const normalizedStatement = normalize(card.statement);
  for (const finding of findings) {
    if (finding.isNoChange) {
      continue;
    }
    const evidenceOverlap = card.evidenceIds.some((id) => finding.contradictedEvidenceIds.has(id));
    const statementOverlap = finding.contradictedStatements.some((statement) => {
      const other = normalize(statement);
      return (
        other.length > 0 &&
        (other === normalizedStatement ||
          other.includes(normalizedStatement) ||
          normalizedStatement.includes(other))
      );
    });
    if (evidenceOverlap || statementOverlap) {
      return finding;
    }
  }
  return null;
}

function operatorCard(hypothesis: HypothesisV1, findings: BiasGuardFinding[]): LedgerCard {
  const statement = hypothesis.statement ?? '';
  const challenge = findChallenge({ statement, evidenceIds: hypothesis.evidenceIds }, findings);
  return {
    id: hypothesis.id,
    statement,
    confidence: hypothesis.confidence ?? null,
    origin: 'operator',
    evidenceIds: hypothesis.evidenceIds,
    challenged: challenge !== null,
    challengeRationale: challenge?.rationale ?? null,
  };
}

/** Agent (ORACLE) hypotheses surfaced from `hypothesis`-type artifacts, best-effort. */
function agentCards(
  sessions: AgentSessionDetailV1[],
  findings: BiasGuardFinding[],
  seenStatements: Set<string>,
): LedgerCard[] {
  const cards: LedgerCard[] = [];
  for (const detail of sessions) {
    if (detail.session.role !== 'ORACLE') {
      continue;
    }
    for (const artifact of detail.artifacts) {
      if (artifact.artifactType !== 'hypothesis') {
        continue;
      }
      const payload = artifact.payload;
      const statement = asString(payload.statement);
      if (!statement) {
        continue;
      }
      const key = normalize(statement);
      if (seenStatements.has(key)) {
        continue;
      }
      seenStatements.add(key);
      const evidenceIds = collectStrings(payload.evidenceIds);
      const challenge = findChallenge({ statement, evidenceIds }, findings);
      cards.push({
        id: artifact.id,
        statement,
        confidence: typeof payload.confidence === 'number' ? payload.confidence : null,
        origin: 'agent',
        evidenceIds,
        challenged: challenge !== null,
        challengeRationale: challenge?.rationale ?? null,
      });
    }
  }
  return cards;
}

/**
 * Build the ledger: operator-pinned hypotheses first (their working theory), then distinct
 * agent hypotheses, each carrying a CHALLENGED flag when a bias-guard finding contradicts it.
 * NO_CHANGE bias checks are collapsed to a count.
 */
export function buildHypothesisLedger(
  operatorHypotheses: HypothesisV1[],
  agentSessions: AgentSessionDetailV1[],
): HypothesisLedger {
  const findings = extractBiasGuardFindings(agentSessions);
  const seenStatements = new Set<string>();

  const operator = operatorHypotheses.map((hypothesis) => {
    const card = operatorCard(hypothesis, findings);
    if (card.statement) {
      seenStatements.add(normalize(card.statement));
    }
    return card;
  });
  const agent = agentCards(agentSessions, findings, seenStatements);

  return {
    cards: [...operator, ...agent],
    collapsedNoChangeCount: findings.filter((finding) => finding.isNoChange).length,
  };
}

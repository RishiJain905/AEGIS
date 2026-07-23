/**
 * Commander's-intent after-action assessment (pure, deterministic — NO LLM).
 *
 * Evaluates the operator's own action record against the intent they stated at launch and
 * returns "held / tension / violated" findings, each with the supporting events. Every check
 * here is a transparent heuristic — labeled as such in the UI — not an authoritative judgement:
 *
 *  - Fuzzy keyword match: the intent is tokenized and matched against asset labels/types to find
 *    the assets/zones the operator named ("protect student records" → the records database).
 *  - Protection of named assets: for each named asset, did an attacker/exfil event reach it, and
 *    did the operator run a containment (Class >= 2) action on it — before or after.
 *  - Evidence preservation: when the intent prioritizes evidence, were destructive commands
 *    (restart/rollback/wipe/reimage) executed that would have destroyed forensic state.
 *  - Containment timing: for a "stop the attacker" intent, did containment land before the first
 *    exfiltration on a protected asset.
 *
 * The function is intentionally input-pure so it can be unit-tested exhaustively; the React
 * component adapts run events/graph into {@link IntentAssessmentInput}.
 */

export type IntentFindingStatus = 'held' | 'tension' | 'violated';

export interface IntentAsset {
  id: string;
  label: string;
  /** assetType from the graph (service/database/identity/…); used as a coarse "zone" signal. */
  kind: string;
}

export interface IntentAction {
  id: string;
  targetAssetId: string;
  /** ActionClass value: "class_0".."class_3". Class 2/3 count as aggressive containment. */
  actionClass: string;
  command: string;
  sequence: number;
}

export interface IntentThreatEvent {
  id: string;
  assetId: string;
  sequence: number;
  /** "exfil" | "attacker" | "alert" — how the threat surfaced on the asset. */
  kind: string;
  label: string;
}

export interface IntentAssessmentInput {
  intent: string;
  assets: IntentAsset[];
  actions: IntentAction[];
  threatEvents: IntentThreatEvent[];
}

export interface IntentFinding {
  id: string;
  status: IntentFindingStatus;
  title: string;
  detail: string;
  /** Event/action ids that ground this finding. */
  supportingEventIds: string[];
}

export interface IntentAssessment {
  intent: string;
  hasIntent: boolean;
  keywords: string[];
  namedAssets: IntentAsset[];
  findings: IntentFinding[];
}

const STOPWORDS = new Set([
  'the',
  'and',
  'for',
  'our',
  'with',
  'that',
  'this',
  'from',
  'into',
  'over',
  'priority',
  'priorities',
  'first',
  'second',
  'third',
  'then',
  'also',
  'keep',
  'protect',
  'protecting',
  'preserve',
  'preserving',
  'preservation',
  'ensure',
  'must',
  'should',
  'while',
  'without',
  'avoid',
  'their',
  'them',
  'are',
  'was',
]);

const AGGRESSIVE_CLASSES = new Set(['class_2', 'class_3']);
const DESTRUCTIVE_COMMAND =
  /\b(restart|reboot|rollback|wipe|reimage|reset|terminate|kill|shutdown|format)\b/i;
const EVIDENCE_THEME =
  /\b(evidence|forensic|forensics|preserv|chain[-\s]?of[-\s]?custody|artifact|log)\b/i;
const STOP_THEME =
  /\b(stop|contain|containment|halt|block|prevent|exfil|attacker|breach|fast|quick|speed)\b/i;

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((token) => token.length >= 3 && !STOPWORDS.has(token));
}

/** A keyword and an asset-label word "fuzzy match" when one contains the other (length >= 4). */
function fuzzyMatches(keyword: string, labelWord: string): boolean {
  if (keyword.length < 4 || labelWord.length < 4) {
    return keyword === labelWord;
  }
  return labelWord.includes(keyword) || keyword.includes(labelWord);
}

function assetNamedByIntent(asset: IntentAsset, keywords: string[]): boolean {
  const labelWords = tokenize(asset.label).concat(asset.kind.toLowerCase());
  return keywords.some((kw) => labelWords.some((lw) => fuzzyMatches(kw, lw)));
}

function firstSequence(items: { sequence: number }[]): number | null {
  if (items.length === 0) {
    return null;
  }
  return items.reduce((min, item) => Math.min(min, item.sequence), Infinity);
}

/** Assess the operator's action record against their commander's intent. Pure + deterministic. */
export function assessIntent(input: IntentAssessmentInput): IntentAssessment {
  const intent = input.intent.trim();
  if (intent.length === 0) {
    return { intent: '', hasIntent: false, keywords: [], namedAssets: [], findings: [] };
  }

  const keywords = Array.from(new Set(tokenize(intent)));
  const namedAssets = input.assets.filter((asset) => assetNamedByIntent(asset, keywords));
  const namedIds = new Set(namedAssets.map((a) => a.id));
  const findings: IntentFinding[] = [];

  const aggressiveActions = input.actions.filter((a) => AGGRESSIVE_CLASSES.has(a.actionClass));

  // 1. Protection of intent-named assets.
  if (namedAssets.length > 0) {
    for (const asset of namedAssets) {
      const threats = input.threatEvents.filter((t) => t.assetId === asset.id);
      const containments = input.actions.filter(
        (a) => a.targetAssetId === asset.id && AGGRESSIVE_CLASSES.has(a.actionClass),
      );
      const firstThreat = firstSequence(threats);
      const firstContainment = firstSequence(containments);
      const supporting = [...threats.map((t) => t.id), ...containments.map((c) => c.id)];

      let status: IntentFindingStatus;
      let detail: string;
      if (firstThreat === null) {
        status = 'held';
        detail = `No attacker activity reached ${asset.label}, which you named as a priority.`;
      } else if (firstContainment === null) {
        status = 'violated';
        detail = `Attacker activity reached ${asset.label} and no containment action was ever run on it.`;
      } else if (firstContainment > firstThreat) {
        status = 'tension';
        detail = `You contained ${asset.label}, but only after attacker activity had already reached it.`;
      } else {
        status = 'held';
        detail = `You contained ${asset.label} before attacker activity reached it.`;
      }
      findings.push({
        id: `intent-protect-${asset.id}`,
        status,
        title: `Protect ${asset.label}`,
        detail,
        supportingEventIds: supporting,
      });
    }
  }

  // 2. Evidence preservation (only when the intent invokes it).
  if (EVIDENCE_THEME.test(intent)) {
    const destructive = input.actions.filter((a) => DESTRUCTIVE_COMMAND.test(a.command));
    let status: IntentFindingStatus;
    let detail: string;
    if (destructive.length > 0) {
      status = 'violated';
      detail = `Your intent prioritized evidence preservation, but ${String(destructive.length)} destructive command(s) (restart/rollback/wipe-class) were executed, which can discard forensic state.`;
    } else if (aggressiveActions.length > 0) {
      status = 'tension';
      detail = `No destructive commands ran, but ${String(aggressiveActions.length)} aggressive containment action(s) were taken — verify they preserved the evidence you prioritized.`;
    } else {
      status = 'held';
      detail = 'No destructive or aggressive actions ran; forensic state was left intact.';
    }
    findings.push({
      id: 'intent-evidence',
      status,
      title: 'Preserve evidence',
      detail,
      supportingEventIds:
        destructive.length > 0 ? destructive.map((a) => a.id) : aggressiveActions.map((a) => a.id),
    });
  }

  // 3. Containment timing vs first exfiltration (for a "stop the attacker" intent).
  if (STOP_THEME.test(intent)) {
    const exfilEvents = input.threatEvents.filter(
      (t) => t.kind === 'exfil' && (namedIds.size === 0 || namedIds.has(t.assetId)),
    );
    const firstExfil = firstSequence(exfilEvents);
    const firstContainment = firstSequence(aggressiveActions);
    if (firstExfil !== null) {
      const supporting = exfilEvents.map((e) => e.id);
      let status: IntentFindingStatus;
      let detail: string;
      if (firstContainment === null) {
        status = 'violated';
        detail = 'Exfiltration occurred and no containment action was taken to stop the attacker.';
        findings.push({
          id: 'intent-containment-timing',
          status,
          title: 'Stop exfiltration',
          detail,
          supportingEventIds: supporting,
        });
      } else {
        status = firstContainment <= firstExfil ? 'held' : 'tension';
        detail =
          firstContainment <= firstExfil
            ? 'You executed containment before the first exfiltration event.'
            : 'Containment landed, but after exfiltration had already begun.';
        findings.push({
          id: 'intent-containment-timing',
          status,
          title: 'Stop exfiltration',
          detail,
          supportingEventIds: supporting.concat(
            aggressiveActions.filter((a) => a.sequence === firstContainment).map((a) => a.id),
          ),
        });
      }
    }
  }

  return { intent, hasIntent: true, keywords, namedAssets, findings };
}

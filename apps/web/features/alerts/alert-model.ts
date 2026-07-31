/**
 * Pure alert-presentation transform: raw alerts + the run's other state -> operator cards.
 *
 * The panel used to render one card per alert row, so a detector that fires on the same
 * asset every window produced a wall of identical "Unseen source activity detected" cards
 * that never mentioned the asset by name and never said what became of it. Everything the
 * operator actually needs is already on the wire — the alert names its asset, the graph
 * knows that asset's current status and label, incidents name the alerts they escalated,
 * and the live timeline records the status transitions that followed. This module is the
 * join, kept React-free so the wording and lifecycle rules are unit-testable.
 */

import type { AlertV1, IncidentV1 } from '@aegis/contracts-ts';

/** A card's headline state. Ordered by precedence — later wins when several apply. */
export type AlertLifecycle = 'new' | 'investigated' | 'superseded' | 'escalated';

/** What happened to the alert's asset *after* the alert fired. */
export interface AlertOutcome {
  status: string;
  sequence: number;
  simTime: string;
}

export interface AlertIncidentRef {
  id: string;
  title: string;
  state: string;
}

/** Minimal per-asset facts the model needs, projected from the operator graph snapshot. */
export interface AssetFacts {
  label: string;
  status: string;
}

/** A status transition read off the live timeline (`sim.asset.status_changed`). */
export interface StatusTransition {
  assetId: string;
  status: string;
  sequence: number;
  simTime: string;
}

/**
 * What an anomaly model reported, when the alert came from one rather than from a rule.
 * Every field is optional at runtime — see {@link readAnomalyDetail}.
 */
export interface AnomalyDetail {
  summary: string | null;
  /** The score the model actually produced, in [0, 1]. */
  observedScore: number | null;
  /** The score it had to beat to fire. */
  threshold: number | null;
  topFeatures: string[];
  modelVersionId: string | null;
}

export interface AlertCard {
  /** Stable across polls: the detector's dedup key when it has one. */
  key: string;
  /** The newest alert in the group — the one whose wording and confidence we show. */
  alert: AlertV1;
  /** How many exact-duplicate alerts folded into this card (1 = not a repeat). */
  count: number;
  assetId: string;
  assetLabel: string;
  assetStatus: string | null;
  firstSequence: number | null;
  lastSequence: number | null;
  firstSimTime: string | null;
  lastSimTime: string | null;
  lifecycle: AlertLifecycle;
  incident: AlertIncidentRef | null;
  /** The status transition this alert preceded, when there is one. */
  outcome: AlertOutcome | null;
  /** Plain-language stakes. Never restates the rule. */
  whyItMatters: string;
  /** The detector's own words, kept for the disclosure. */
  detectorDetail: string | null;
  /** The model's own words, when an anomaly detector raised this. */
  anomaly: AnomalyDetail | null;
}

export interface BuildAlertCardsInput {
  alerts: AlertV1[];
  incidents: IncidentV1[];
  /** assetId -> label + current status, from the operator-facing graph snapshot. */
  assets: Map<string, AssetFacts>;
  /** Status transitions seen this session, ascending or not — order is not assumed. */
  transitions?: StatusTransition[];
  /** Alert keys the operator has already opened in this session. */
  openedKeys?: ReadonlySet<string>;
}

/** Statuses that mean somebody — operator or agent — has already picked the alert up. */
const TRIAGED_STATUSES = new Set(['under_investigation', 'contained']);

/**
 * Group key for exact-duplicate collapsing. The detector's `deduplicationKey` is the
 * authoritative answer; the composite fallback keeps pre-dedup alerts from each other's
 * cards while still folding a repeating detector into one.
 */
export function alertGroupKey(alert: AlertV1): string {
  return alert.deduplicationKey ?? `${alert.assetId}|${alert.title}|${alert.detectorId ?? 'rule'}`;
}

/** `2026-01-01T00:02:30.000Z` -> `00:02:30`. Falls back to the raw value. */
export function simClock(timestamp: string | null | undefined): string {
  if (!timestamp) {
    return '—';
  }
  return /T(\d{2}:\d{2}:\d{2})/.exec(timestamp)?.[1] ?? timestamp;
}

/** Human status wording, for prose rather than the status chip. */
function statusWord(status: string): string {
  return status.replace(/_/g, ' ');
}

function alertSequence(alert: AlertV1): number | null {
  return alert.evidence?.sequenceEnd ?? null;
}

function alertSimTime(alert: AlertV1): string | null {
  return alert.evidence?.simTimeEnd ?? alert.createdAt;
}

/**
 * The plain-language "so what". Built only from facts on hand: what the asset's status
 * became, whether a case was opened, and whether the signal is repeating. It says what
 * changed and what it costs the operator to ignore — never what the rule computed.
 */
function explainStakes(params: {
  assetLabel: string;
  assetStatus: string | null;
  count: number;
  incident: AlertIncidentRef | null;
  outcome: AlertOutcome | null;
  superseded: boolean;
}): string {
  const { assetLabel, assetStatus, count, incident, outcome, superseded } = params;

  if (outcome?.status === 'compromised') {
    return `${assetLabel} was confirmed compromised at ${simClock(outcome.simTime)}. This alert saw it first.`;
  }
  if (outcome?.status === 'contained') {
    return `${assetLabel} has been contained since ${simClock(outcome.simTime)}. Nothing further is required here.`;
  }
  if (incident) {
    return `Escalated into ${incident.title}, now ${statusWord(incident.state)}.`;
  }
  if (assetStatus && TRIAGED_STATUSES.has(assetStatus)) {
    return `${assetLabel} is already ${statusWord(assetStatus)}. This alert is part of that case.`;
  }
  if (superseded) {
    return `A newer alert on ${assetLabel} has overtaken this one. Work the newer signal.`;
  }
  if (count > 1) {
    return `${String(count)} sightings on ${assetLabel} and still nothing has changed. The signal is repeating, not resolving.`;
  }
  return `First sighting on ${assetLabel}. Its status has not moved yet — open the asset or keep watching.`;
}

/** The detector's own sentence, for operators who want to audit the rule. */
function detectorDetail(alert: AlertV1): string | null {
  const explanation = alert.explanation;
  if (!explanation) {
    return null;
  }
  return `${explanation.condition} — ${explanation.comparison}`;
}

function readNumber(source: Record<string, unknown>, key: string): number | null {
  const value = source[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function readString(source: Record<string, unknown>, key: string): string | null {
  const value = source[key];
  return typeof value === 'string' && value.length > 0 ? value : null;
}

/**
 * Read an anomaly detector's account of itself off the alert.
 *
 * `AlertV1.anomalyExplanation` is typed as an open record rather than the strict
 * `anomalyExplanationSchema`, so every field is read defensively: a model that ships a new
 * payload shape must cost the operator one line of the disclosure, not the card.
 */
export function readAnomalyDetail(alert: AlertV1): AnomalyDetail | null {
  // Typed as `unknown` on purpose: the contract promises a record, but this is the one
  // field on the alert that a model owns end-to-end, so the guards below have to be real
  // runtime checks rather than ones the compiler can prove away.
  const raw: unknown = alert.anomalyExplanation;
  if (typeof raw !== 'object' || raw === null) {
    return null;
  }
  const source = raw as Record<string, unknown>;
  const topFeatures = Array.isArray(source['topFeatures'])
    ? source['topFeatures'].filter((value): value is string => typeof value === 'string')
    : [];

  return {
    summary: readString(source, 'summary'),
    // The score is what the operator is being asked to trust; when the model omitted it,
    // the alert's own confidence is the same number by another name.
    observedScore: readNumber(source, 'observedScore') ?? alert.confidence ?? null,
    threshold: readNumber(source, 'threshold'),
    topFeatures,
    modelVersionId: readString(source, 'modelVersionId') ?? alert.modelVersionId ?? null,
  };
}

/**
 * Build the panel's cards: newest first, exact duplicates folded, each card carrying the
 * asset it names, that asset's current status, the case it fed, and what happened next.
 */
export function buildAlertCards(input: BuildAlertCardsInput): AlertCard[] {
  const { alerts, incidents, assets } = input;
  const transitions = input.transitions ?? [];
  const openedKeys = input.openedKeys ?? new Set<string>();

  const incidentByAlertId = new Map<string, AlertIncidentRef>();
  for (const incident of incidents) {
    // Read defensively: an incident that arrives without its alert links must cost the
    // operator an escalation marker, not the whole alerts rail. The contract requires the
    // field, so the runtime guard is deliberately wider than the type.
    const alertIds: string[] = Array.isArray(incident.alertIds) ? incident.alertIds : [];
    for (const alertId of alertIds) {
      incidentByAlertId.set(alertId, {
        id: incident.id,
        title: incident.title,
        state: incident.state,
      });
    }
  }

  const groups = new Map<string, AlertV1[]>();
  for (const alert of alerts) {
    const key = alertGroupKey(alert);
    const bucket = groups.get(key);
    if (bucket) {
      bucket.push(alert);
    } else {
      groups.set(key, [alert]);
    }
  }

  const draft = [...groups.entries()].map(([key, members]) => {
    const ordered = [...members].sort(
      (left, right) => (alertSequence(left) ?? 0) - (alertSequence(right) ?? 0),
    );
    const newest = ordered[ordered.length - 1] as AlertV1;
    const oldest = ordered[0] as AlertV1;
    const facts = assets.get(newest.assetId) ?? null;
    const incident =
      ordered.map((alert) => incidentByAlertId.get(alert.id)).find((ref) => ref != null) ?? null;

    return {
      key,
      alert: newest,
      count: ordered.length,
      assetId: newest.assetId,
      assetLabel: facts?.label ?? newest.assetId,
      assetStatus: facts?.status ?? null,
      firstSequence: alertSequence(oldest),
      lastSequence: alertSequence(newest),
      firstSimTime: alertSimTime(oldest),
      lastSimTime: alertSimTime(newest),
      incident,
      detectorDetail: detectorDetail(newest),
      anomaly: readAnomalyDetail(newest),
    };
  });

  // Newest signal at the top: an operator scanning the rail reads down from "just landed".
  draft.sort((left, right) => (right.lastSequence ?? 0) - (left.lastSequence ?? 0));

  const newestSequenceByAsset = new Map<string, number>();
  for (const card of draft) {
    const current = newestSequenceByAsset.get(card.assetId) ?? -1;
    newestSequenceByAsset.set(card.assetId, Math.max(current, card.lastSequence ?? -1));
  }

  return draft.map((card) => {
    // The alert's consequence: the latest status change on its asset at or after it fired.
    // Transitions before the alert belong to an earlier signal, so they are not this
    // card's outcome; of the ones that follow, the latest is where the asset stands now.
    const latestTransition = transitions
      .filter(
        (transition) =>
          transition.assetId === card.assetId && transition.sequence >= (card.firstSequence ?? 0),
      )
      .sort((left, right) => left.sequence - right.sequence)
      .at(-1);
    const outcome: AlertOutcome | null = latestTransition
      ? {
          status: latestTransition.status,
          sequence: latestTransition.sequence,
          simTime: latestTransition.simTime,
        }
      : null;

    const superseded =
      card.lastSequence !== null &&
      (newestSequenceByAsset.get(card.assetId) ?? -1) > card.lastSequence;

    const investigated =
      openedKeys.has(card.key) ||
      (card.assetStatus !== null && TRIAGED_STATUSES.has(card.assetStatus));

    const lifecycle: AlertLifecycle = card.incident
      ? 'escalated'
      : superseded
        ? 'superseded'
        : investigated
          ? 'investigated'
          : 'new';

    return {
      ...card,
      lifecycle,
      outcome,
      whyItMatters: explainStakes({
        assetLabel: card.assetLabel,
        assetStatus: card.assetStatus,
        count: card.count,
        incident: card.incident,
        outcome,
        superseded,
      }),
    };
  });
}

export const LIFECYCLE_LABEL: Record<AlertLifecycle, string> = {
  new: 'New',
  investigated: 'Investigated',
  superseded: 'Superseded',
  escalated: 'Escalated',
};

/** A hidden cause the scenario has stopped hiding, in operator language. */
export interface RevealNote {
  key: string;
  sequence: number;
  simTime: string;
  /** The cause, already humanised by the timeline projector. */
  cause: string;
  /** Assets whose status moved at or after the reveal — what it cost. */
  assetLabels: string[];
}

/** How far past a reveal a status change is still read as part of that reveal. */
const REVEAL_FALLOUT_SEQUENCES = 12;

/**
 * Read hidden-condition reveals off the live timeline and attach their fallout.
 *
 * A reveal is the scenario admitting *why* things went wrong — the one moment where an
 * operator can connect the alerts they were chasing to the cause underneath them. The graph
 * already flashes a six-second pulse when an asset becomes visible (`RevealAnnouncer`); this
 * is the durable, explained counterpart that survives the operator looking away.
 */
export function readReveals(
  entries: readonly { eventType: string; label: string; sequence: number; timestamp: string }[],
  assets: Map<string, AssetFacts>,
): RevealNote[] {
  const transitions = readStatusTransitions(entries);
  const notes: RevealNote[] = [];
  for (const entry of entries) {
    if (entry.eventType !== 'sim.hidden_condition.revealed') {
      continue;
    }
    const cause = entry.label.replace(/^Underlying cause revealed:\s*/i, '');
    const assetLabels = [
      ...new Set(
        transitions
          .filter(
            (transition) =>
              transition.sequence >= entry.sequence &&
              transition.sequence <= entry.sequence + REVEAL_FALLOUT_SEQUENCES,
          )
          .map((transition) => assets.get(transition.assetId)?.label ?? transition.assetId),
      ),
    ];
    notes.push({
      key: `${String(entry.sequence)}:${cause}`,
      sequence: entry.sequence,
      simTime: entry.timestamp,
      cause,
      assetLabels,
    });
  }
  return notes.sort((left, right) => right.sequence - left.sequence);
}

/**
 * Pull the status transitions out of the live timeline. The projector writes these as
 * `Asset asset:x → compromised`; the asset id is matched defensively so a wording change
 * degrades to "no outcome known" rather than a wrong one.
 */
export function readStatusTransitions(
  entries: readonly { eventType: string; label: string; sequence: number; timestamp: string }[],
): StatusTransition[] {
  const transitions: StatusTransition[] = [];
  for (const entry of entries) {
    if (entry.eventType !== 'sim.asset.status_changed') {
      continue;
    }
    const match = /(asset:[\w.:-]+)\s*→\s*(\w+)/.exec(entry.label);
    if (!match?.[1] || !match[2]) {
      continue;
    }
    transitions.push({
      assetId: match[1],
      status: match[2],
      sequence: entry.sequence,
      simTime: entry.timestamp,
    });
  }
  return transitions;
}

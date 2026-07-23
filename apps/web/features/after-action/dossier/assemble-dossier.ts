/**
 * Adversary dossier assembly — pure, deterministic reconstruction of the attacker
 * campaign and the defender response from a run's authoritative event stream.
 *
 * This module NEVER performs I/O and NEVER reaches for an LLM: every narrative caption
 * is a template string derived from event data, so it runs identically in CI and in the
 * browser. It is the post-run debrief lens — callers MUST only feed it a terminated run's
 * events (the after-action page gates on terminal status), because the raw stream is full
 * ground truth and would leak the attacker's position mid-run.
 *
 * Attacker lane  = covert world changes the operator could not see until detection:
 *   - `sim.hidden_condition.triggered` (an attack beat activates)
 *   - `sim.asset.status_changed` driven by the SYSTEM actor into a worse state
 * Defender lane  = everything the operator/agents did in response:
 *   - alerts, incidents, agent tasks, operator proposals/approvals/executions, RoE changes
 * Detection crossings = the moments fog lifts (a reveal event, or the first alert on a
 *   covert asset) — rendered where the two lanes cross.
 *
 * Undetected dwell for a beat = time from the beat until it is disclosed (its reveal event
 * or the first alert on its asset), or until run end if never detected.
 */

import type { RunScoreV1 } from '@aegis/contracts-ts';

/* ------------------------------------------------------------------ */
/* Input event shape (lenient — tolerant of registry drift)            */
/* ------------------------------------------------------------------ */

/**
 * A minimal, defensively-typed view of a domain event. We deliberately do NOT reuse the
 * strict `domainEventEnvelopeSchema` here: the Python event registry emits types the TS
 * contract registry has not yet caught up on (Phase 7 `operator.action.proposed`,
 * `run.roe_changed`, `autonomy.task.enqueued`, `report.*`), and a strict parse throws on
 * the whole batch when one unknown type appears. The dossier must degrade, never crash.
 */
export interface DossierEvent {
  sequence: number;
  type: string;
  simTime: string;
  actorType: string;
  actorId: string;
  subjectType: string;
  subjectId: string;
  payload: Record<string, unknown>;
}

/* ------------------------------------------------------------------ */
/* Output view model                                                   */
/* ------------------------------------------------------------------ */

export type AttackerBeatKind = 'condition_triggered' | 'asset_effect';

export interface AttackerBeat {
  id: string;
  sequence: number;
  simTime: string;
  kind: AttackerBeatKind;
  label: string;
  conditionId?: string;
  assetId?: string;
  assetLabel?: string;
  status?: string;
  detected: boolean;
  detectedAtSimTime?: string;
  detectedBySequence?: number;
  /** Seconds the beat sat undetected (until disclosure, or run end if never detected). */
  dwellSeconds: number;
}

export type DefenderActionKind =
  | 'alert'
  | 'incident'
  | 'agent_task'
  | 'operator_action'
  | 'approval'
  | 'execution'
  | 'roe_change'
  | 'command';

export interface DefenderAction {
  id: string;
  sequence: number;
  simTime: string;
  kind: DefenderActionKind;
  label: string;
  initiator?: 'operator' | 'autonomy' | 'agent' | 'system';
  assetId?: string;
  assetLabel?: string;
  status?: string;
}

export interface DetectionCrossing {
  id: string;
  simTime: string;
  attackerBeatId: string;
  defenderActionId?: string;
  label: string;
  dwellSeconds: number;
}

export interface DossierKeyMoments {
  runStartSimTime?: string;
  firstBreachSimTime?: string;
  firstDetectionSimTime?: string;
  containmentSimTime?: string;
  runEndSimTime?: string;
  /** firstBreach -> firstDetection: the operator's opening blind window. */
  timeToDetectionSeconds?: number;
  /** Union of every beat's undetected interval (no double-counting of overlaps). */
  totalUndetectedDwellSeconds: number;
}

export type ExfilStatus = 'contained' | 'detected_uncontained' | 'undetected';

export interface ExfilOutcome {
  status: ExfilStatus;
  label: string;
  detail: string;
}

export interface AdversaryDossierViewModel {
  runId: string;
  rootCauseBranchId?: string;
  rootCauseLabel: string;
  rootCauseKnown: boolean;
  objectivesOutcome: { passed: boolean; grade: string; overallPct: number } | null;
  exfilOutcome: ExfilOutcome;
  keyMoments: DossierKeyMoments;
  attackerBeats: AttackerBeat[];
  defenderActions: DefenderAction[];
  crossings: DetectionCrossing[];
  /** Merged, chronologically-ordered rows for the linearized (a11y / mobile) view. */
  timeline: DossierTimelineRow[];
}

export interface DossierTimelineRow {
  id: string;
  side: 'attacker' | 'defender' | 'crossing';
  sequence: number;
  simTime: string;
  label: string;
  detail?: string;
}

/* ------------------------------------------------------------------ */
/* Constants                                                           */
/* ------------------------------------------------------------------ */

const ATTACKER_STATUSES = new Set(['compromised', 'suspicious', 'under_investigation', 'degraded']);

const DEFENDER_EVENT_KIND: Record<string, DefenderActionKind> = {
  'alert.created': 'alert',
  'incident.created': 'incident',
  'incident.state_changed': 'incident',
  'agent.task.started': 'agent_task',
  'agent.task.completed': 'agent_task',
  'agent.task.failed': 'agent_task',
  'operator.action.proposed': 'operator_action',
  'action.proposal.created': 'operator_action',
  'action.proposal.approved': 'approval',
  'action.proposal.rejected': 'approval',
  'action.executed': 'execution',
  'sim.command.executed': 'command',
  'run.roe_changed': 'roe_change',
};

/* ------------------------------------------------------------------ */
/* Small deterministic helpers                                         */
/* ------------------------------------------------------------------ */

function toMillis(iso: string): number {
  const ms = Date.parse(iso);
  return Number.isNaN(ms) ? 0 : ms;
}

export function secondsBetween(fromIso: string, toIso: string): number {
  return Math.max(0, Math.round((toMillis(toIso) - toMillis(fromIso)) / 1000));
}

/** Human-readable duration: "6m 12s", "2h 03m", "48s". */
export function formatDwell(seconds: number): string {
  if (seconds <= 0) {
    return '0s';
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) {
    return `${String(h)}h ${String(m).padStart(2, '0')}m`;
  }
  if (m > 0) {
    return `${String(m)}m ${String(s).padStart(2, '0')}s`;
  }
  return `${String(s)}s`;
}

/** Turn an id like `asset:identity-svc-logistics-bot` into `Identity Svc Logistics Bot`. */
export function humanizeAssetId(assetId: string): string {
  const tail = assetId.includes(':') ? assetId.slice(assetId.indexOf(':') + 1) : assetId;
  return tail
    .split(/[-_]/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/** `branch-cause-credentials` / `hidden-cause-compromised-credentials` -> readable label. */
export function humanizeCauseId(id: string): string {
  const stripped = id
    .replace(/^branch-cause-/, '')
    .replace(/^hidden-cause-/, '')
    .replace(/^branch-/, '');
  const words = stripped.split(/[-_]/).filter(Boolean);
  if (words.length === 0) {
    return id;
  }
  return words.map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w)).join(' ');
}

/**
 * Total length (seconds) of the union of a set of half-open intervals. Overlapping
 * undetected windows are counted once, so the aggregate dwell is honest.
 */
export function intervalUnionSeconds(intervals: readonly (readonly [number, number])[]): number {
  const valid = intervals
    .map(([a, b]) => [a, Math.max(a, b)] as const)
    .filter(([a, b]) => b > a)
    .sort((x, y) => x[0] - y[0]);
  let totalMs = 0;
  let curStart = Number.NaN;
  let curEnd = Number.NaN;
  for (const [s, e] of valid) {
    if (Number.isNaN(curStart)) {
      curStart = s;
      curEnd = e;
      continue;
    }
    if (s <= curEnd) {
      curEnd = Math.max(curEnd, e);
    } else {
      totalMs += curEnd - curStart;
      curStart = s;
      curEnd = e;
    }
  }
  if (!Number.isNaN(curStart)) {
    totalMs += curEnd - curStart;
  }
  return Math.round(totalMs / 1000);
}

function label(
  assetId: string | undefined,
  assetLabels: Record<string, string>,
): string | undefined {
  if (!assetId) {
    return undefined;
  }
  return assetLabels[assetId] ?? humanizeAssetId(assetId);
}

function payloadString(payload: Record<string, unknown>, key: string): string | undefined {
  const value = payload[key];
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

/* ------------------------------------------------------------------ */
/* Assembly                                                            */
/* ------------------------------------------------------------------ */

export interface AssembleDossierInput {
  runId: string;
  events: readonly DossierEvent[];
  score?: RunScoreV1 | null;
  /** Sim time the run ended; falls back to the last event's sim time. */
  runEndSimTime?: string;
  runStartSimTime?: string;
  /** Optional assetId -> display label map (post-run graph); ids humanize when absent. */
  assetLabels?: Record<string, string>;
}

export function assembleAdversaryDossier(input: AssembleDossierInput): AdversaryDossierViewModel {
  const assetLabels = input.assetLabels ?? {};
  const events = [...input.events].sort((a, b) => a.sequence - b.sequence);

  const runStartSimTime =
    input.runStartSimTime ??
    events.find((e) => e.type === 'sim.run.started')?.simTime ??
    events[0]?.simTime;
  const runEndSimTime =
    input.runEndSimTime ??
    events.find((e) => e.type === 'sim.run.stopped')?.simTime ??
    events[events.length - 1]?.simTime ??
    runStartSimTime;

  /* --- disclosure signals ------------------------------------------------ */
  // reveal sim time per condition id
  const revealBySimTime = new Map<string, string>();
  // earliest alert sim time (+ sequence) per asset id
  const firstAlertByAsset = new Map<string, { simTime: string; sequence: number }>();
  let firstRevealSimTime: string | undefined;

  for (const event of events) {
    if (event.type === 'sim.hidden_condition.revealed') {
      const conditionId = payloadString(event.payload, 'conditionId');
      if (conditionId && !revealBySimTime.has(conditionId)) {
        revealBySimTime.set(conditionId, event.simTime);
      }
      if (firstRevealSimTime === undefined) {
        firstRevealSimTime = event.simTime;
      }
    } else if (event.type === 'alert.created') {
      const assetId = payloadString(event.payload, 'assetId');
      if (assetId && !firstAlertByAsset.has(assetId)) {
        firstAlertByAsset.set(assetId, { simTime: event.simTime, sequence: event.sequence });
      }
    }
  }

  /* --- root cause -------------------------------------------------------- */
  const rootCauseBranch = events.find(
    (e) =>
      e.type === 'sim.branch.selected' && payloadString(e.payload, 'branchGroup') === 'root-cause',
  );
  const rootCauseBranchId = rootCauseBranch
    ? payloadString(rootCauseBranch.payload, 'branchId')
    : undefined;
  const scoreCauseLabel = input.score?.hiddenCauseLabel ?? undefined;
  const rootCauseKnown = Boolean(scoreCauseLabel ?? rootCauseBranchId);
  const rootCauseLabel =
    scoreCauseLabel ??
    (rootCauseBranchId ? humanizeCauseId(rootCauseBranchId) : 'Undetermined root cause');

  /* --- attacker beats ---------------------------------------------------- */
  const attackerBeats: AttackerBeat[] = [];
  const crossings: DetectionCrossing[] = [];

  for (const event of events) {
    if (event.type === 'sim.hidden_condition.triggered') {
      const conditionId = payloadString(event.payload, 'conditionId');
      const revealSimTime = conditionId ? revealBySimTime.get(conditionId) : undefined;
      const detected = Boolean(revealSimTime);
      const disclosureSimTime = revealSimTime ?? runEndSimTime;
      const dwellSeconds = secondsBetween(event.simTime, disclosureSimTime ?? event.simTime);
      const causeLabel = conditionId ? humanizeCauseId(conditionId) : 'covert activity';
      const beat: AttackerBeat = {
        id: `beat-${String(event.sequence)}`,
        sequence: event.sequence,
        simTime: event.simTime,
        kind: 'condition_triggered',
        label: `Attack beat activated — ${causeLabel}`,
        conditionId: conditionId ?? undefined,
        detected,
        detectedAtSimTime: revealSimTime,
        dwellSeconds,
      };
      attackerBeats.push(beat);
      continue;
    }

    if (event.type === 'sim.asset.status_changed') {
      const status = payloadString(event.payload, 'status');
      const assetId = payloadString(event.payload, 'assetId') ?? event.subjectId;
      const isAttackerDriven =
        event.actorType === 'system' && status !== undefined && ATTACKER_STATUSES.has(status);
      if (!isAttackerDriven) {
        continue; // containment / recovery — handled in the defender lane
      }
      const alert = firstAlertByAsset.get(assetId);
      const detected = Boolean(alert && toMillis(alert.simTime) >= toMillis(event.simTime));
      const disclosureSimTime = detected ? alert?.simTime : runEndSimTime;
      const dwellSeconds = secondsBetween(event.simTime, disclosureSimTime ?? event.simTime);
      const assetLabel = label(assetId, assetLabels);
      const beat: AttackerBeat = {
        id: `beat-${String(event.sequence)}`,
        sequence: event.sequence,
        simTime: event.simTime,
        kind: 'asset_effect',
        label: `${assetLabel ?? assetId} driven to ${status}`,
        assetId,
        assetLabel,
        status,
        detected,
        detectedAtSimTime: detected ? alert?.simTime : undefined,
        detectedBySequence: detected ? alert?.sequence : undefined,
        dwellSeconds,
      };
      attackerBeats.push(beat);
    }
  }

  /* --- defender actions -------------------------------------------------- */
  const defenderActions: DefenderAction[] = [];
  for (const event of events) {
    const kind = DEFENDER_EVENT_KIND[event.type];
    if (!kind) {
      continue;
    }
    // A system-actor status change to a benign state is a containment world-note; only
    // surface it if it represents recovery, otherwise skip telemetry noise.
    const assetId =
      payloadString(event.payload, 'assetId') ??
      payloadString(event.payload, 'targetAssetId') ??
      undefined;
    const assetLabel = label(assetId, assetLabels);
    const initiator = payloadString(event.payload, 'initiator') as
      | DefenderAction['initiator']
      | undefined;
    defenderActions.push({
      id: `def-${String(event.sequence)}`,
      sequence: event.sequence,
      simTime: event.simTime,
      kind,
      label: defenderLabel(event, assetLabel),
      initiator: initiator ?? defaultInitiator(event),
      assetId,
      assetLabel,
      status: payloadString(event.payload, 'status'),
    });
  }

  /* --- detection crossings ---------------------------------------------- */
  for (const beat of attackerBeats) {
    if (!beat.detected || !beat.detectedAtSimTime) {
      continue;
    }
    const defenderAction =
      beat.detectedBySequence !== undefined
        ? defenderActions.find((d) => d.sequence === beat.detectedBySequence)
        : undefined;
    crossings.push({
      id: `cross-${beat.id}`,
      simTime: beat.detectedAtSimTime,
      attackerBeatId: beat.id,
      defenderActionId: defenderAction?.id,
      label: `Detected: ${beat.label}`,
      dwellSeconds: beat.dwellSeconds,
    });
  }
  crossings.sort((a, b) => toMillis(a.simTime) - toMillis(b.simTime));

  /* --- key moments ------------------------------------------------------- */
  const firstBreachSimTime = attackerBeats[0]?.simTime;
  const firstAlertSimTime = [...firstAlertByAsset.values()].sort(
    (a, b) => toMillis(a.simTime) - toMillis(b.simTime),
  )[0]?.simTime;
  const firstDetectionSimTime = earliest(firstRevealSimTime, firstAlertSimTime);
  const containmentSimTime = earliest(
    defenderActions.find((d) => d.kind === 'execution')?.simTime,
    events.find(
      (e) =>
        e.type === 'sim.asset.status_changed' && payloadString(e.payload, 'status') === 'contained',
    )?.simTime,
  );

  const undetectedIntervals: (readonly [number, number])[] = attackerBeats.map((beat) => {
    const end = beat.detected && beat.detectedAtSimTime ? beat.detectedAtSimTime : runEndSimTime;
    return [toMillis(beat.simTime), toMillis(end ?? beat.simTime)] as const;
  });

  const keyMoments: DossierKeyMoments = {
    runStartSimTime,
    firstBreachSimTime,
    firstDetectionSimTime,
    containmentSimTime,
    runEndSimTime,
    timeToDetectionSeconds:
      firstBreachSimTime && firstDetectionSimTime
        ? secondsBetween(firstBreachSimTime, firstDetectionSimTime)
        : undefined,
    totalUndetectedDwellSeconds: intervalUnionSeconds(undetectedIntervals),
  };

  /* --- exfil / breach outcome ------------------------------------------- */
  const exfilOutcome = deriveExfilOutcome({
    attackerBeats,
    hiddenCauseRevealed: input.score?.hiddenCauseRevealed ?? Boolean(firstRevealSimTime),
    contained: containmentSimTime !== undefined,
  });

  /* --- objectives -------------------------------------------------------- */
  const objectivesOutcome = input.score
    ? {
        passed: input.score.passed,
        grade: input.score.grade,
        overallPct: Math.round((input.score.overallScore / input.score.maxScore) * 100),
      }
    : null;

  /* --- linearized timeline (a11y) --------------------------------------- */
  const timeline = buildLinearTimeline(attackerBeats, defenderActions, crossings);

  return {
    runId: input.runId,
    rootCauseBranchId,
    rootCauseLabel,
    rootCauseKnown,
    objectivesOutcome,
    exfilOutcome,
    keyMoments,
    attackerBeats,
    defenderActions,
    crossings,
    timeline,
  };
}

/* ------------------------------------------------------------------ */
/* Label + outcome derivation                                          */
/* ------------------------------------------------------------------ */

function defenderLabel(event: DossierEvent, assetLabel: string | undefined): string {
  const p = event.payload;
  switch (event.type) {
    case 'alert.created': {
      const title = payloadString(p, 'title') ?? 'anomaly detected';
      return assetLabel ? `Alert: ${title} on ${assetLabel}` : `Alert: ${title}`;
    }
    case 'incident.created':
      return `Incident opened: ${payloadString(p, 'title') ?? 'investigation'}`;
    case 'incident.state_changed':
      return `Incident → ${payloadString(p, 'toState') ?? payloadString(p, 'state') ?? 'updated'}`;
    case 'agent.task.started':
      return 'Agent tasked to investigate';
    case 'agent.task.completed':
      return 'Agent finding posted';
    case 'agent.task.failed':
      return 'Agent task failed';
    case 'operator.action.proposed': {
      const command = payloadString(p, 'scenarioCommand') ?? 'containment';
      return assetLabel
        ? `Operator proposed ${command} on ${assetLabel}`
        : `Operator proposed ${command}`;
    }
    case 'action.proposal.created':
      return 'Containment proposal created';
    case 'action.proposal.approved':
      return assetLabel ? `Approved containment on ${assetLabel}` : 'Approved containment';
    case 'action.proposal.rejected':
      return 'Rejected containment proposal';
    case 'action.executed':
      return assetLabel ? `Executed containment on ${assetLabel}` : 'Executed containment';
    case 'sim.command.executed':
      return `Operator command: ${payloadString(p, 'commandType') ?? 'step'}`;
    case 'run.roe_changed':
      return `Rules of engagement → ${payloadString(p, 'newRoe') ?? 'changed'}`;
    default:
      return event.type;
  }
}

function defaultInitiator(event: DossierEvent): DefenderAction['initiator'] {
  if (event.actorType === 'operator') {
    return 'operator';
  }
  if (event.actorType === 'agent') {
    return 'agent';
  }
  return 'system';
}

function deriveExfilOutcome(args: {
  attackerBeats: readonly AttackerBeat[];
  hiddenCauseRevealed: boolean;
  contained: boolean;
}): ExfilOutcome {
  const anyBeats = args.attackerBeats.length > 0;
  const allDetected = anyBeats && args.attackerBeats.every((b) => b.detected);
  if (args.contained && (args.hiddenCauseRevealed || allDetected)) {
    return {
      status: 'contained',
      label: 'Contained',
      detail: 'The attacker campaign was detected and a containment action was executed.',
    };
  }
  if (args.hiddenCauseRevealed || args.attackerBeats.some((b) => b.detected)) {
    return {
      status: 'detected_uncontained',
      label: 'Detected, uncontained',
      detail: 'The campaign surfaced through detection but no containment action was executed.',
    };
  }
  return {
    status: 'undetected',
    label: 'Undetected',
    detail: anyBeats
      ? 'The attacker operated to run end without being surfaced by detection.'
      : 'No covert attacker activity was recorded for this run.',
  };
}

function earliest(...times: (string | undefined)[]): string | undefined {
  const present = times.filter((t): t is string => Boolean(t));
  if (present.length === 0) {
    return undefined;
  }
  return present.reduce((a, b) => (toMillis(a) <= toMillis(b) ? a : b));
}

function buildLinearTimeline(
  attackerBeats: readonly AttackerBeat[],
  defenderActions: readonly DefenderAction[],
  crossings: readonly DetectionCrossing[],
): DossierTimelineRow[] {
  const rows: DossierTimelineRow[] = [];
  for (const beat of attackerBeats) {
    rows.push({
      id: beat.id,
      side: 'attacker',
      sequence: beat.sequence,
      simTime: beat.simTime,
      label: beat.label,
      detail: beat.detected
        ? `Undetected for ${formatDwell(beat.dwellSeconds)}`
        : `Undetected for ${formatDwell(beat.dwellSeconds)} — never surfaced`,
    });
  }
  for (const action of defenderActions) {
    rows.push({
      id: action.id,
      side: 'defender',
      sequence: action.sequence,
      simTime: action.simTime,
      label: action.label,
      detail: action.initiator ? `by ${action.initiator}` : undefined,
    });
  }
  for (const crossing of crossings) {
    rows.push({
      id: crossing.id,
      side: 'crossing',
      sequence: 0,
      simTime: crossing.simTime,
      label: crossing.label,
      detail: `Dwell ${formatDwell(crossing.dwellSeconds)}`,
    });
  }
  return rows.sort((a, b) => {
    const byTime = toMillis(a.simTime) - toMillis(b.simTime);
    return byTime !== 0 ? byTime : a.sequence - b.sequence;
  });
}

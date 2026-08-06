/**
 * Operator prose for a feed entry.
 *
 * The console API composes a feed entry's `summary` from the raw event name — literally
 * `sim.hidden_condition.revealed` or `agent.task.failed (asset:device-analyst-01)` — so the
 * Chronicle was reading the wire back to the operator. The room already speaks this
 * vocabulary elsewhere: the timeline projector renders the same events as "Underlying cause
 * revealed: Vendor key reuse", and the action model turns command traffic into "Isolate host
 * on Analyst workstation". This is that vocabulary for the plain entries neither of those
 * two covers.
 *
 * Pure and total: an event type with no phrasing yet degrades to a readable sentence built
 * from its own name rather than to a dotted identifier, so a new backend event is never
 * unreadable and never blocks the feed.
 */

import type { RunFeedEntry } from '@/features/command-surface';

/** The `type (asset:id)` shape the API's summary fallback produces. */
const RAW_SUMMARY = /^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+(\s+\([^)]*\))?$/;

/** True when the entry's summary is the event name rather than a sentence about it. */
export function isRawSummary(summary: string): boolean {
  return RAW_SUMMARY.test(summary.trim());
}

function payloadText(payload: Record<string, unknown>, ...keys: string[]): string | null {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === 'string' && value.length > 0) {
      return value;
    }
  }
  return null;
}

/**
 * `condition-vendor-key-reuse` -> `Vendor key reuse`. Mirrors the timeline projector's
 * reading of the same id, so the tape and the Chronicle name a cause identically.
 */
export function humaniseConditionId(conditionId: string): string {
  const words = conditionId
    .replace(/^(hidden[-_]?)?condition[-_]?/i, '')
    .split(/[-_.]+/)
    .filter(Boolean);
  if (words.length === 0) {
    return 'an undisclosed cause';
  }
  const [first, ...rest] = words as [string, ...string[]];
  return [first.charAt(0).toUpperCase() + first.slice(1), ...rest].join(' ');
}

/** Last-resort phrasing: `agent.task.failed` -> `Agent task failed`. */
function humaniseEventType(eventType: string): string {
  const words = eventType.split(/[.\-_]+/).filter(Boolean);
  if (words.length === 0) {
    return eventType;
  }
  const [first, ...rest] = words as [string, ...string[]];
  return [first.charAt(0).toUpperCase() + first.slice(1), ...rest].join(' ');
}

/** The role an agent event belongs to, upper-cased as the roles are always written. */
function roleOf(payload: Record<string, unknown>): string | null {
  return payloadText(payload, 'role', 'agentRole')?.toUpperCase() ?? null;
}

/**
 * One entry, said the way an operator would say it. Returns `null` when the entry already
 * carries prose the backend or another model wrote — this only speaks for raw summaries.
 */
function phraseFor(entry: RunFeedEntry): string | null {
  const payload = entry.payload;
  const asset = payloadText(payload, 'assetId', 'targetAssetId', 'subjectId');
  const role = roleOf(payload);
  const on = asset ? ` on ${asset}` : '';

  switch (entry.type) {
    case 'sim.hidden_condition.revealed':
      return `Underlying cause revealed: ${humaniseConditionId(
        payloadText(payload, 'conditionId') ?? 'unknown',
      )}`;
    case 'sim.hidden_condition.triggered':
      return `Underlying cause active: ${humaniseConditionId(
        payloadText(payload, 'conditionId') ?? 'unknown',
      )}`;
    case 'sim.asset.status_changed':
      return `${asset ?? 'An asset'} is now ${payloadText(payload, 'status') ?? 'updated'}`;
    case 'sim.run.started':
      return 'Run started';
    case 'sim.run.paused':
      return 'Run paused';
    case 'sim.run.resumed':
      return 'Run resumed';
    case 'sim.run.stopped':
      return 'Run stopped';
    case 'alert.created':
      return `Alert raised${on}: ${payloadText(payload, 'title') ?? 'detector fired'}`;
    case 'alert.updated':
      return `Alert updated${on}`;
    case 'incident.created':
      return `Incident opened: ${payloadText(payload, 'title') ?? 'new case'}`;
    case 'incident.updated':
      return `Incident updated: ${payloadText(payload, 'title') ?? 'case changed'}`;
    case 'risk.score.computed':
      return `Graph risk updated${on}`;
    case 'risk.projection.updated':
      return 'Graph risk projection updated';
    case 'agent.task.created':
      return `${role ?? 'An agent'} picked up a task${on}`;
    case 'agent.task.completed':
      return `${role ?? 'An agent'} finished its task${on}`;
    case 'agent.task.failed': {
      // The backend's terminal event carries the attributable cause
      // (errorMessage/errorCode); older events only had free-form error/message.
      const reason = payloadText(payload, 'errorMessage', 'error', 'message');
      const code = payloadText(payload, 'errorCode');
      return `${role ?? 'An agent'} could not finish its task${on}${
        reason === null ? '' : ` — ${reason}`
      }${code === null ? '' : ` (${code})`}`;
    }
    case 'agent.artifact.created':
      return `${role ?? 'An agent'} recorded a finding${on}`;
    case 'investigation.updated':
      return 'Investigation record updated';
    case 'report.generation.completed':
      return 'After-action report generated';
    case 'report.version.created':
      return 'After-action report version recorded';
    default:
      return null;
  }
}

/**
 * What a feed row should say. Prefers the backend's own sentence when it wrote one; falls
 * back to the room's vocabulary, and finally to a humanised form of the event name so
 * nothing ever renders as a dotted identifier.
 */
export function describeEntry(entry: RunFeedEntry): string {
  if (!isRawSummary(entry.summary)) {
    return entry.summary;
  }
  const phrase = phraseFor(entry);
  if (phrase !== null) {
    return phrase;
  }
  const asset = payloadText(entry.payload, 'assetId', 'targetAssetId', 'subjectId');
  const humanised = humaniseEventType(entry.type);
  return asset ? `${humanised} on ${asset}` : humanised;
}

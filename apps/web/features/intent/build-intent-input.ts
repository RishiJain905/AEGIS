/**
 * Adapt a terminated run's graph + event stream into the pure {@link IntentAssessmentInput}.
 *
 * Kept pure and separate from the React hook so the event→input mapping is unit-testable. All
 * signals are derived from ground-truth events (safe post-run only):
 *  - assets: graph nodes (id, label, assetType).
 *  - containment actions: `sim.asset.status_changed` → "contained", plus any command-bearing
 *    action event (so destructive commands are visible to the evidence check).
 *  - threat events: attacker status transitions (compromised/suspicious), hidden-condition
 *    reveals/triggers, exfil-typed events, and raised alerts.
 */

import type { GraphNodeV1 } from '@aegis/contracts-ts';

import type { IntentAction, IntentAssessmentInput, IntentThreatEvent } from './assess-intent';
import type { IntentEvent } from './fetch-intent-events';

const ADVERSARY_STATUSES = new Set(['compromised', 'suspicious']);
const HIDDEN_CONDITION_TYPES = new Set([
  'sim.hidden_condition.revealed',
  'sim.hidden_condition.triggered',
]);

export function buildIntentInput(
  intent: string | null | undefined,
  nodes: GraphNodeV1[],
  events: IntentEvent[],
): IntentAssessmentInput {
  const assets = nodes
    .filter((node) => node.entityType === 'asset')
    .map((node) => ({ id: node.id, label: node.label, kind: node.assetType }));

  const actions: IntentAction[] = [];
  const threatEvents: IntentThreatEvent[] = [];

  for (const event of events) {
    const isContainment = event.type === 'sim.asset.status_changed' && event.status === 'contained';
    const hasCommand = event.command.length > 0;
    if (isContainment || hasCommand) {
      actions.push({
        id: event.eventId,
        targetAssetId: event.assetId,
        actionClass: 'class_2',
        command: event.command,
        sequence: event.sequence,
      });
    }

    const isAttackerStatus =
      event.type === 'sim.asset.status_changed' && ADVERSARY_STATUSES.has(event.status);
    const isHiddenCondition = HIDDEN_CONDITION_TYPES.has(event.type);
    const isExfil = /exfil/i.test(event.type) || /exfil/i.test(event.label);
    const isAlert = event.type === 'alert.created';
    if ((isAttackerStatus || isHiddenCondition || isExfil || isAlert) && event.assetId) {
      threatEvents.push({
        id: event.eventId,
        assetId: event.assetId,
        sequence: event.sequence,
        kind: isExfil ? 'exfil' : isAlert ? 'alert' : 'attacker',
        label: event.label || event.type,
      });
    }
  }

  return { intent: intent ?? '', assets, actions, threatEvents };
}

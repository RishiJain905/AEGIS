/**
 * Pure action-card transform for the ops feed.
 *
 * The feed used to render command traffic as its raw event name — `EXECUTED … action.executed`
 * and `OPERATOR … operator.action.proposed (asset:svc-identity-broker)` — which is unauditable:
 * a reviewer cannot tell what was done, to what, under whose authority, or with what effect.
 * Every one of those facts is already on the wire, just spread across sibling events that
 * share a `proposalId`. This module performs that join and resolves the command's own catalogue
 * entry (label, class, consequence) so the feed can render an action the way it was ordered.
 *
 * React-free and total: an event with a still-settling payload degrades to fewer fields, never
 * to a wrong one.
 */

import {
  ACTION_CLASS_LABEL,
  COMMAND_CATALOGUE,
  type ActionClass,
  type RunFeedEntry,
} from '@/features/command-surface';

/** Where the action stands in the policy → approval → execution pipeline. */
export type ActionStage =
  | 'proposed'
  | 'awaiting approval'
  | 'blocked'
  | 'rejected'
  | 'executed'
  | 'cancelled';

export interface ActionCardModel {
  /** What was ordered, in the operator's own vocabulary ("Isolate", "Revoke credentials"). */
  verb: string;
  /** The asset the order names — `null` when the event stream never bound one. */
  targetAssetId: string | null;
  actionClass: ActionClass | null;
  actionClassLabel: string | null;
  stage: ActionStage;
  /** Policy engine verdict, when one has been recorded for this proposal. */
  policyOutcome: string | null;
  /** What the order does to the estate, from the command catalogue. */
  impact: string | null;
  /** Whether the effect can be walked back. */
  reversible: boolean | null;
  /** The operator's stated reason, when the event stream carried one. */
  justification: string | null;
  incidentId: string | null;
}

/** Feed categories whose entries are command traffic rather than commentary. */
const ACTION_CATEGORIES = new Set(['operator_action', 'execution', 'approval', 'proposal']);

function payloadText(payload: Record<string, unknown>, ...keys: string[]): string | null {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === 'string' && value.length > 0) {
      return value;
    }
  }
  return null;
}

function commandLabel(command: string): string {
  return (
    COMMAND_CATALOGUE.find((meta) => meta.command === command)?.label ??
    command.replace(/_/g, ' ').replace(/^./, (character) => character.toUpperCase())
  );
}

function isActionClass(value: string | null): value is ActionClass {
  return value === 'class_0' || value === 'class_1' || value === 'class_2' || value === 'class_3';
}

interface ProposalFacts {
  command: string | null;
  actionClass: ActionClass | null;
  targetAssetId: string | null;
  justification: string | null;
  policyOutcome: string | null;
  approved: boolean;
  rejected: boolean;
  cancelled: boolean;
  executed: boolean;
}

/**
 * Fold every event that mentions a proposal into one record of that proposal.
 *
 * This is what makes an `action.executed` — which carries only ids — renderable: the command,
 * class and target came in on the `operator.action.proposed` event that shares its id.
 */
export function buildProposalFacts(entries: readonly RunFeedEntry[]): Map<string, ProposalFacts> {
  const facts = new Map<string, ProposalFacts>();

  const factsFor = (proposalId: string): ProposalFacts => {
    const existing = facts.get(proposalId);
    if (existing) {
      return existing;
    }
    const created: ProposalFacts = {
      command: null,
      actionClass: null,
      targetAssetId: null,
      justification: null,
      policyOutcome: null,
      approved: false,
      rejected: false,
      cancelled: false,
      executed: false,
    };
    facts.set(proposalId, created);
    return created;
  };

  for (const entry of entries) {
    const proposalId = payloadText(entry.payload, 'proposalId');
    if (proposalId === null) {
      continue;
    }
    const record = factsFor(proposalId);
    const command = payloadText(entry.payload, 'scenarioCommand', 'command', 'commandId');
    if (command !== null && record.command === null) {
      record.command = command;
    }
    const actionClass = payloadText(entry.payload, 'actionClass');
    if (isActionClass(actionClass) && record.actionClass === null) {
      record.actionClass = actionClass;
    }
    const target = payloadText(entry.payload, 'targetAssetId', 'assetId');
    if (target !== null && record.targetAssetId === null) {
      record.targetAssetId = target;
    }
    const justification = payloadText(entry.payload, 'justification', 'rationale', 'reason');
    if (justification !== null && record.justification === null) {
      record.justification = justification;
    }
    if (entry.type.startsWith('policy.')) {
      record.policyOutcome = payloadText(entry.payload, 'outcome') ?? record.policyOutcome;
    }
    if (entry.type === 'action.proposal.approved') {
      record.approved = true;
    }
    if (entry.type === 'action.proposal.rejected') {
      record.rejected = true;
    }
    if (entry.type === 'action.proposal.cancelled') {
      record.cancelled = true;
    }
    if (entry.type === 'action.executed') {
      record.executed = true;
    }
  }

  return facts;
}

function stageFor(entry: RunFeedEntry, record: ProposalFacts | undefined): ActionStage {
  if (entry.type === 'action.executed') {
    return 'executed';
  }
  if (entry.type === 'action.proposal.rejected' || record?.rejected === true) {
    return 'rejected';
  }
  if (entry.type === 'action.proposal.cancelled' || record?.cancelled === true) {
    return 'cancelled';
  }
  if (record?.executed === true) {
    return 'executed';
  }
  if (record?.approved === true) {
    return 'executed';
  }
  // A policy block is not a human rejection: nothing was reviewed, the engine refused it.
  // The distinction matters when auditing the feed, so the stages stay separate.
  if (payloadText(entry.payload, 'outcome') === 'block' || record?.policyOutcome === 'block') {
    return 'blocked';
  }
  if (record?.policyOutcome === 'approval_required') {
    return 'awaiting approval';
  }
  return 'proposed';
}

/**
 * Describe one feed entry as a typed action card, or `null` when it is not command traffic.
 *
 * `facts` comes from {@link buildProposalFacts} over the whole feed, so a card can name the
 * command and target even when its own event carried only ids.
 */
export function describeAction(
  entry: RunFeedEntry,
  facts: Map<string, ProposalFacts>,
): ActionCardModel | null {
  if (!ACTION_CATEGORIES.has(entry.category)) {
    return null;
  }
  const proposalId = payloadText(entry.payload, 'proposalId');
  const record = proposalId !== null ? facts.get(proposalId) : undefined;

  const command =
    payloadText(entry.payload, 'scenarioCommand', 'command') ?? record?.command ?? null;
  if (command === null) {
    // No command anywhere in the proposal's event trail — an approval-only or policy-only
    // entry. The generic row still renders it; a typed card would be inventing detail.
    return null;
  }

  const catalogue = COMMAND_CATALOGUE.find((meta) => meta.command === command) ?? null;
  const actionClass =
    (isActionClass(payloadText(entry.payload, 'actionClass'))
      ? (payloadText(entry.payload, 'actionClass') as ActionClass)
      : null) ??
    record?.actionClass ??
    catalogue?.actionClass ??
    null;

  return {
    verb: commandLabel(command),
    targetAssetId:
      payloadText(entry.payload, 'targetAssetId', 'assetId') ?? record?.targetAssetId ?? null,
    actionClass,
    actionClassLabel: actionClass ? ACTION_CLASS_LABEL[actionClass] : null,
    stage: stageFor(entry, record),
    policyOutcome: payloadText(entry.payload, 'outcome') ?? record?.policyOutcome ?? null,
    impact: catalogue?.consequence ?? null,
    reversible: catalogue?.reversible ?? null,
    justification:
      payloadText(entry.payload, 'justification', 'rationale', 'reason') ??
      record?.justification ??
      null,
    incidentId: payloadText(entry.payload, 'incidentId'),
  };
}

import { describe, expect, it } from 'vitest';

import type { RunFeedEntry } from '@/features/command-surface';

import { buildProposalFacts, describeAction } from './action-model';

const ASSET = 'asset:svc-identity-broker';

function entry(overrides: Partial<RunFeedEntry> & { sequence: number }): RunFeedEntry {
  return {
    schemaVersion: 1,
    eventId: `evt-${String(overrides.sequence)}`,
    type: 'operator.action.proposed',
    category: 'operator_action',
    simTime: '2026-01-01T00:02:30.000Z',
    initiator: 'operator',
    summary: 'operator.action.proposed',
    payload: {},
    ...overrides,
  };
}

const proposed = entry({
  sequence: 10,
  payload: {
    proposalId: 'prop_1',
    incidentId: 'incident:inc_1',
    scenarioCommand: 'isolate',
    actionClass: 'class_2',
    targetAssetId: ASSET,
    initiator: 'operator',
  },
});

const executed = entry({
  sequence: 12,
  type: 'action.executed',
  category: 'execution',
  summary: 'action.executed',
  payload: {
    proposalId: 'prop_1',
    incidentId: 'incident:inc_1',
    approvalId: 'apr_1',
    executedActionId: 'act_1',
    commandId: 'cmd_1',
  },
});

describe('describeAction', () => {
  it('recovers command, class and target for an execution event that carries only ids', () => {
    const facts = buildProposalFacts([proposed, executed]);
    const action = describeAction(executed, facts);

    expect(action).not.toBeNull();
    expect(action?.verb).toBe('Isolate');
    expect(action?.targetAssetId).toBe(ASSET);
    expect(action?.actionClass).toBe('class_2');
    expect(action?.actionClassLabel).toBe('Class 2 · Operational');
    expect(action?.stage).toBe('executed');
    expect(action?.incidentId).toBe('incident:inc_1');
  });

  it('carries the command catalogue impact and reversibility so the feed states consequences', () => {
    const facts = buildProposalFacts([proposed, executed]);
    const action = describeAction(executed, facts);

    expect(action?.impact).toContain('Severs the asset from the network');
    expect(action?.reversible).toBe(true);
  });

  it('flags a non-reversible class 3 command', () => {
    const rollback = entry({
      sequence: 20,
      payload: {
        proposalId: 'prop_2',
        scenarioCommand: 'rollback_deployment',
        targetAssetId: ASSET,
      },
    });
    const action = describeAction(rollback, buildProposalFacts([rollback]));
    expect(action?.verb).toBe('Rollback deployment');
    expect(action?.actionClass).toBe('class_3');
    expect(action?.reversible).toBe(false);
  });

  it('reports the policy verdict and awaiting-approval stage', () => {
    const policy = entry({
      sequence: 11,
      type: 'policy.evaluated',
      category: 'policy',
      payload: { proposalId: 'prop_1', outcome: 'approval_required' },
    });
    const facts = buildProposalFacts([proposed, policy]);
    const action = describeAction(proposed, facts);

    expect(action?.policyOutcome).toBe('approval_required');
    expect(action?.stage).toBe('awaiting approval');
  });

  it('reports a policy block as blocked — distinct from a human rejection', () => {
    const policy = entry({
      sequence: 11,
      type: 'policy.evaluated',
      category: 'policy',
      payload: { proposalId: 'prop_1', outcome: 'block' },
    });
    const facts = buildProposalFacts([proposed, policy]);
    expect(describeAction(proposed, facts)?.stage).toBe('blocked');
    expect(describeAction(proposed, facts)?.policyOutcome).toBe('block');
  });

  it('never lets a policy block shadow an actual execution', () => {
    const policy = entry({
      sequence: 11,
      type: 'policy.evaluated',
      category: 'policy',
      payload: { proposalId: 'prop_1', outcome: 'block' },
    });
    const facts = buildProposalFacts([proposed, policy, executed]);
    expect(describeAction(executed, facts)?.stage).toBe('executed');
  });

  it('reports a rejected proposal as rejected rather than proposed', () => {
    const rejected = entry({
      sequence: 13,
      type: 'action.proposal.rejected',
      category: 'proposal',
      payload: { proposalId: 'prop_1', reason: 'Too disruptive during business hours' },
    });
    const facts = buildProposalFacts([proposed, rejected]);
    expect(describeAction(proposed, facts)?.stage).toBe('rejected');
    expect(describeAction(rejected, facts)?.justification).toBe(
      'Too disruptive during business hours',
    );
  });

  it('picks up the operator justification wherever the event stream records it', () => {
    const withReason = entry({
      sequence: 14,
      payload: {
        proposalId: 'prop_3',
        scenarioCommand: 'restrict_access',
        targetAssetId: ASSET,
        justification: 'Failed authentication burst from an unseen source',
      },
    });
    const action = describeAction(withReason, buildProposalFacts([withReason]));
    expect(action?.justification).toBe('Failed authentication burst from an unseen source');
  });

  it('declines to type an entry that is not command traffic', () => {
    const finding = entry({ sequence: 30, type: 'agent.task.completed', category: 'agent' });
    expect(describeAction(finding, buildProposalFacts([finding]))).toBeNull();
  });

  it('declines to type command traffic whose proposal never named a command', () => {
    const approval = entry({
      sequence: 31,
      type: 'action.proposal.approved',
      category: 'approval',
      payload: { proposalId: 'prop_unknown', approvalId: 'apr_9' },
    });
    expect(describeAction(approval, buildProposalFacts([approval]))).toBeNull();
  });
});

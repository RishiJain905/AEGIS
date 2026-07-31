import { describe, expect, it } from 'vitest';

import type { DomainEventEnvelopeV1, GraphSnapshotV1 } from '@aegis/contracts-ts';

import { projectDomainEventToActions } from '@/lib/realtime/event-projector';
import { createInitialRunReplicatedState, runReplicatedReducer } from '@/lib/realtime/run-reducer';

const baseEvent: DomainEventEnvelopeV1 = {
  eventId: 'evt_proj_001',
  runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
  sequence: 1,
  type: 'sim.run.started',
  schemaVersion: 1,
  simTime: '2026-01-01T00:00:00.000Z',
  recordedAt: '2026-01-01T00:00:00.000Z',
  actor: { type: 'system', id: 'asset:simulation-engine' },
  subject: { type: 'system', id: 'asset:simulation-engine' },
  payload: { schemaVersion: 1 },
  traceId: 'trc_proj_001',
};

const knownNode: GraphSnapshotV1['nodes'][number] = {
  schemaVersion: 1,
  id: 'asset:svc-identity-broker',
  entityType: 'asset',
  assetType: 'service',
  label: 'Identity Broker',
  riskScore: 0.4,
  criticality: 0.8,
  status: 'compromised',
  revision: 3,
  disclosed: true,
};

function project(event: DomainEventEnvelopeV1, knownNodes = new Map([[knownNode.id, knownNode]])) {
  return projectDomainEventToActions(event, {
    lastAppliedSequence: event.sequence - 1,
    seenEventIds: new Set<string>(),
    knownNodes,
  });
}

describe('run lifecycle projection', () => {
  it('does not turn the run outcome verdict into a run status', () => {
    // `sim.run.outcome_resolved` announces who won; the run record stays `running` until
    // the ticker stops it. Deriving a status from the event name published
    // `outcome_resolved` as the header's run status, so the header claimed the run had
    // ended while after-action, reports and replay all still (correctly) read `running`.
    const actions = project({
      ...baseEvent,
      eventId: 'evt_outcome',
      sequence: 5,
      type: 'sim.run.outcome_resolved',
      payload: { schemaVersion: 1, outcome: 'win', reason: 'all_campaigns_neutralized' },
    });

    expect(actions.some((action) => action.type === 'update_run_status')).toBe(false);
    // The sequence still advances, so the client does not gap-detect on the verdict.
    expect(actions).toContainEqual(
      expect.objectContaining({ type: 'advance_sequence', sequence: 5 }),
    );
  });

  it('keeps the header on the last real lifecycle transition across a verdict', () => {
    let state = createInitialRunReplicatedState(baseEvent.runId);
    for (const event of [
      baseEvent,
      {
        ...baseEvent,
        eventId: 'evt_outcome',
        sequence: 2,
        type: 'sim.run.outcome_resolved',
        payload: { schemaVersion: 1, outcome: 'loss_exfiltration' },
      },
    ]) {
      for (const action of projectDomainEventToActions(event, {
        lastAppliedSequence: state.lastAppliedSequence,
        seenEventIds: new Set(state.seenEventIds),
        knownNodes: new Map(),
      })) {
        state = runReplicatedReducer(state, action);
      }
    }

    expect(state.runStatus).toBe('running');
    expect(state.lastAppliedSequence).toBe(2);
  });

  it('still maps the four real lifecycle transitions', () => {
    const cases: Array<[string, string]> = [
      ['sim.run.started', 'running'],
      ['sim.run.resumed', 'running'],
      ['sim.run.paused', 'paused'],
      ['sim.run.stopped', 'stopped'],
    ];
    for (const [type, expected] of cases) {
      const actions = project({ ...baseEvent, eventId: `evt_${type}`, sequence: 4, type });
      expect(actions).toContainEqual(
        expect.objectContaining({ type: 'update_run_status', runStatus: expected }),
      );
    }
  });
});

describe('asset status projection', () => {
  it('projects a containment world status onto the graph vocabulary', () => {
    // The payload carries the response-toolkit status the operator's action produced.
    // Handing `isolated` to the graph store leaves the node holding a status the
    // inspector, legend and status-presentation table have no entry for.
    const actions = project({
      ...baseEvent,
      eventId: 'evt_isolated',
      sequence: 2,
      type: 'sim.asset.status_changed',
      subject: { type: 'asset', id: knownNode.id },
      payload: { schemaVersion: 1, assetId: knownNode.id, status: 'isolated' },
    });

    const delta = actions.find((action) => action.type === 'apply_graph_delta');
    expect(delta).toBeDefined();
    expect(delta?.type === 'apply_graph_delta' ? delta.delta.node?.status : undefined).toBe(
      'contained',
    );

    const timeline = actions.find((action) => action.type === 'append_timeline_entry');
    expect(timeline?.type === 'append_timeline_entry' ? timeline.entry.status : undefined).toBe(
      'contained',
    );
    // The tape keeps naming the actual control, so the operator can audit what was done.
    expect(timeline?.type === 'append_timeline_entry' ? timeline.entry.label : '').toContain(
      'isolated',
    );
  });

  it('passes an attacker-driven status through unchanged', () => {
    const actions = project({
      ...baseEvent,
      eventId: 'evt_compromised',
      sequence: 2,
      type: 'sim.asset.status_changed',
      subject: { type: 'asset', id: knownNode.id },
      payload: { schemaVersion: 1, assetId: knownNode.id, status: 'compromised' },
    });

    const delta = actions.find((action) => action.type === 'apply_graph_delta');
    expect(delta?.type === 'apply_graph_delta' ? delta.delta.node?.status : undefined).toBe(
      'compromised',
    );
  });

  it('records an observation without erasing the compromise underneath it', () => {
    // The defect this covers: "Observe" overwrote the node's status, so watching a
    // compromised host made it look merely under investigation and the intrusion
    // vanished from the operator's view.
    const actions = project({
      ...baseEvent,
      eventId: 'evt_observed',
      sequence: 2,
      type: 'sim.asset.status_changed',
      subject: { type: 'asset', id: knownNode.id },
      payload: { schemaVersion: 1, assetId: knownNode.id, status: 'observed' },
    });

    const delta = actions.find((action) => action.type === 'apply_graph_delta');
    const node = delta?.type === 'apply_graph_delta' ? delta.delta.node : undefined;
    expect(node?.status).toBe('compromised');
    expect(node?.appliedControls).toEqual(['observed']);
  });

  it('accumulates controls so a later isolation still remembers the observation', () => {
    const observed = { ...knownNode, appliedControls: ['observed'] };
    const actions = project(
      {
        ...baseEvent,
        eventId: 'evt_then_isolated',
        sequence: 3,
        type: 'sim.asset.status_changed',
        subject: { type: 'asset', id: observed.id },
        payload: { schemaVersion: 1, assetId: observed.id, status: 'isolated' },
      },
      new Map([[observed.id, observed]]),
    );

    const delta = actions.find((action) => action.type === 'apply_graph_delta');
    const node = delta?.type === 'apply_graph_delta' ? delta.delta.node : undefined;
    expect(node?.status).toBe('contained');
    expect(node?.appliedControls).toEqual(['observed', 'isolated']);
  });
});

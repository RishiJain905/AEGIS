import { describe, expect, it } from 'vitest';

import type { AgentSessionDetailV1, HypothesisV1 } from '@aegis/contracts-ts';

import { buildHypothesisLedger } from './ledger-model';

function hypothesis(overrides: Partial<HypothesisV1> & { id: string }): HypothesisV1 {
  return {
    schemaVersion: 1,
    incidentId: 'incident:inc_operatorconsole',
    status: 'active',
    statement: 'The logistics API is the initial access point.',
    confidence: 0.6,
    evidenceIds: [],
    createdAt: '2026-07-22T00:00:00.000Z',
    ...overrides,
  } as HypothesisV1;
}

function oracleSession(
  overrides: {
    tasks?: Partial<AgentSessionDetailV1['tasks'][number]>[];
    artifacts?: Partial<AgentSessionDetailV1['artifacts'][number]>[];
  } = {},
): AgentSessionDetailV1 {
  return {
    schemaVersion: 1,
    session: {
      schemaVersion: 1,
      id: 'agent-session:sess_oracle',
      runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      incidentId: null,
      role: 'ORACLE',
      status: 'completed',
      initiator: 'autonomy',
      traceId: 'trc_00000000000000000000000000',
      createdAt: '2026-07-22T00:00:00.000Z',
      updatedAt: '2026-07-22T00:00:00.000Z',
    },
    tasks: (overrides.tasks ?? []).map((task, index) => ({
      schemaVersion: 1,
      id: `agent-task:task_${String(index)}`,
      sessionId: 'agent-session:sess_oracle',
      runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      incidentId: null,
      status: 'completed',
      attempt: 1,
      idempotencyKey: `idem-${String(index)}`,
      traceId: 'trc_00000000000000000000000000',
      providerId: 'provider:mock',
      initiator: 'autonomy',
      createdAt: '2026-07-22T00:00:00.000Z',
      updatedAt: '2026-07-22T00:00:00.000Z',
      ...task,
    })) as AgentSessionDetailV1['tasks'],
    transitions: [],
    toolInvocations: [],
    artifacts: (overrides.artifacts ?? []).map((artifact, index) => ({
      schemaVersion: 1,
      id: `agent-artifact:art_${String(index)}`,
      taskId: `agent-task:task_${String(index)}`,
      sessionId: 'agent-session:sess_oracle',
      artifactType: 'step_result',
      payload: {},
      createdAt: '2026-07-22T00:00:00.000Z',
      ...artifact,
    })) as AgentSessionDetailV1['artifacts'],
    budget: null,
  } as unknown as AgentSessionDetailV1;
}

describe('buildHypothesisLedger', () => {
  it('renders operator hypotheses as un-challenged cards with no agent activity', () => {
    const ledger = buildHypothesisLedger([hypothesis({ id: 'hyp:1' })], []);
    expect(ledger.cards).toHaveLength(1);
    expect(ledger.cards[0]).toMatchObject({ origin: 'operator', challenged: false });
    expect(ledger.collapsedNoChangeCount).toBe(0);
  });

  it('badges a hypothesis CHALLENGED when a bias-guard finding shares its evidence', () => {
    const session = oracleSession({
      tasks: [{ instructions: 'Bias guard: re-examine the leading hypothesis.' }],
      artifacts: [
        {
          artifactType: 'step_result',
          payload: {
            rationale: 'New auth failures contradict the logistics-access theory.',
            contradictingEvidenceIds: ['evidence:ev_9'],
          },
        },
      ],
    });
    const ledger = buildHypothesisLedger(
      [hypothesis({ id: 'hyp:1', evidenceIds: ['evidence:ev_9'] })],
      [session],
    );
    expect(ledger.cards[0]?.challenged).toBe(true);
    expect(ledger.cards[0]?.challengeRationale).toContain('contradict');
  });

  it('badges by statement overlap when evidence ids do not line up', () => {
    const statement = 'The logistics API is the initial access point.';
    const session = oracleSession({
      tasks: [{ instructions: 'Bias guard: check the leading hypothesis.' }],
      artifacts: [
        {
          artifactType: 'step_result',
          payload: {
            rationale: 'Evidence conflicts with the stated theory.',
            hypotheses: [{ statement, contradictingEvidenceIds: ['evidence:ev_1'] }],
          },
        },
      ],
    });
    const ledger = buildHypothesisLedger([hypothesis({ id: 'hyp:1', statement })], [session]);
    expect(ledger.cards[0]?.challenged).toBe(true);
  });

  it('collapses NO_CHANGE bias checks into a count and does not badge', () => {
    const session = oracleSession({
      tasks: [{ instructions: 'Bias guard: re-examine the leading hypothesis.' }],
      artifacts: [
        {
          artifactType: 'step_result',
          payload: { rationale: 'NO_CHANGE — the leading hypothesis still holds.' },
        },
      ],
    });
    const ledger = buildHypothesisLedger([hypothesis({ id: 'hyp:1' })], [session]);
    expect(ledger.cards[0]?.challenged).toBe(false);
    expect(ledger.collapsedNoChangeCount).toBe(1);
  });

  it('surfaces distinct agent hypotheses and dedupes against operator statements', () => {
    const operatorStatement = 'The logistics API is the initial access point.';
    const session = oracleSession({
      artifacts: [
        {
          artifactType: 'hypothesis',
          payload: { statement: 'Credentials were compromised.', confidence: 0.7 },
        },
        {
          artifactType: 'hypothesis',
          payload: { statement: operatorStatement, confidence: 0.5 },
        },
      ],
    });
    const ledger = buildHypothesisLedger(
      [hypothesis({ id: 'hyp:1', statement: operatorStatement })],
      [session],
    );
    const agentCards = ledger.cards.filter((card) => card.origin === 'agent');
    expect(agentCards).toHaveLength(1);
    expect(agentCards[0]?.statement).toBe('Credentials were compromised.');
  });

  it('ignores bias-guard tasks that are not autonomous', () => {
    const session = oracleSession({
      tasks: [{ instructions: 'Bias guard: re-examine.', initiator: 'operator' }],
      artifacts: [
        {
          artifactType: 'step_result',
          payload: { contradictingEvidenceIds: ['evidence:ev_9'] },
        },
      ],
    });
    const ledger = buildHypothesisLedger(
      [hypothesis({ id: 'hyp:1', evidenceIds: ['evidence:ev_9'] })],
      [session],
    );
    expect(ledger.cards[0]?.challenged).toBe(false);
  });
});

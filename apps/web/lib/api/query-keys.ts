export const queryKeys = {
  scenarios: {
    all: ['scenarios'] as const,
    detail: (scenarioId: string) => ['scenarios', scenarioId] as const,
    versions: (scenarioId: string) => ['scenarios', scenarioId, 'versions'] as const,
  },
  runs: {
    all: ['runs'] as const,
    detail: (runId: string) => ['runs', runId] as const,
    incidents: (runId: string) => ['runs', runId, 'incidents'] as const,
    alerts: (runId: string) => ['runs', runId, 'alerts'] as const,
    riskScores: (runId: string) => ['runs', runId, 'risk-scores'] as const,
    graph: (runId: string) => ['runs', runId, 'graph'] as const,
    readOnly: (runId: string) => ['runs', runId, 'read-only'] as const,
    afterActionReport: (runId: string) => ['runs', runId, 'after-action-report'] as const,
    afterAction: (runId: string) => ['runs', runId, 'after-action'] as const,
    score: (runId: string) => ['runs', runId, 'score'] as const,
    reportVersions: (runId: string) => ['runs', runId, 'report-versions'] as const,
  },
  incidents: {
    detail: (incidentId: string) => ['incidents', incidentId] as const,
    investigation: (incidentId: string) => ['incidents', incidentId, 'investigation'] as const,
  },
  agentSessions: {
    detail: (sessionId: string) => ['agent-sessions', sessionId] as const,
    listForRun: (runId: string) => ['runs', runId, 'agent-sessions'] as const,
  },
  connection: {
    status: ['connection', 'status'] as const,
  },
  replay: {
    state: (runId: string, sequence: number, incidentId?: string | null) =>
      ['replay', runId, 'state', sequence, incidentId ?? null] as const,
    cursor: (runId: string, sequence: number) => ['replay', runId, 'cursor', sequence] as const,
    diff: (runId: string, fromSequence: number, toSequence: number) =>
      ['replay', runId, 'diff', fromSequence, toSequence] as const,
    snapshots: (runId: string) => ['replay', runId, 'snapshots'] as const,
  },
} as const;

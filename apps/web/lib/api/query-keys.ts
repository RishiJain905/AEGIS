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
    reportVersions: (runId: string) => ['runs', runId, 'report-versions'] as const,
  },
  incidents: {
    detail: (incidentId: string) => ['incidents', incidentId] as const,
    investigation: (incidentId: string) => ['incidents', incidentId, 'investigation'] as const,
  },
  agentSessions: {
    detail: (sessionId: string) => ['agent-sessions', sessionId] as const,
  },
  connection: {
    status: ['connection', 'status'] as const,
  },
} as const;

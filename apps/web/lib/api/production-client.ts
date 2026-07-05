import {
  agentSessionDetailSchema,
  apiErrorEnvelopeSchema,
  graphSnapshotSchema,
  investigationDetailSchema,
  parseContract,
  riskScoresListResponseSchema,
} from '@aegis/contracts-ts';

import type { AegisApiClient, ConnectionStatus, RunGraphResult } from '@/lib/api/types';
import { ApiClientError } from '@/lib/api/types';

function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
}

async function fetchJson<T>(
  path: string,
  signal?: AbortSignal,
  parser?: (data: unknown) => T,
): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    signal,
    headers: { Accept: 'application/json' },
  });

  if (!response.ok) {
    let envelope;
    try {
      const body: unknown = await response.json();
      envelope = parseContract(apiErrorEnvelopeSchema, body);
    } catch {
      throw new ApiClientError({
        code: 'HTTP_ERROR',
        message: `Request failed with status ${String(response.status)}`,
        status: response.status,
      });
    }
    throw new ApiClientError({
      code: envelope.code,
      message: envelope.message,
      status: response.status,
      traceId: envelope.traceId,
    });
  }

  const data: unknown = await response.json();
  return parser ? parser(data) : (data as T);
}

export function createProductionClient(): AegisApiClient {
  return {
    listScenarios: (signal) => fetchJson('/api/v1/scenarios', signal),
    getScenario: (scenarioId, signal) => fetchJson(`/api/v1/scenarios/${scenarioId}`, signal),
    listScenarioVersions: (scenarioId, signal) =>
      fetchJson(`/api/v1/scenarios/${scenarioId}/versions`, signal),
    getRun: (runId, signal) => fetchJson(`/api/v1/runs/${runId}`, signal),
    listRuns: (signal) => fetchJson('/api/v1/runs', signal),
    listIncidents: (runId, signal) => fetchJson(`/api/v1/runs/${runId}/incidents`, signal),
    getIncident: (incidentId, signal) => fetchJson(`/api/v1/incidents/${incidentId}`, signal),
    getInvestigationDetail: (incidentId, signal) =>
      fetchJson(`/api/v1/incidents/${incidentId}/investigation`, signal, (data) =>
        parseContract(investigationDetailSchema, data),
      ),
    getAgentSession: (sessionId, signal) =>
      fetchJson(`/api/v1/agent-sessions/${sessionId}`, signal, (data) =>
        parseContract(agentSessionDetailSchema, data),
      ),
    listAlerts: (runId, signal) => fetchJson(`/api/v1/runs/${runId}/alerts`, signal),
    listRiskScores: async (runId, signal) => {
      const response = await fetchJson(`/api/v1/risk/scores/${runId}`, signal, (data) =>
        parseContract(riskScoresListResponseSchema, data),
      );
      return response.scores;
    },
    getRunGraph: async (runId, signal): Promise<RunGraphResult> => {
      try {
        const snapshot = await fetchJson(`/api/v1/runs/${runId}/graph`, signal, (data) =>
          parseContract(graphSnapshotSchema, data),
        );
        return { snapshot, partial: false };
      } catch (error) {
        if (error instanceof ApiClientError && error.status === 404) {
          return { snapshot: null, partial: true };
        }
        throw error;
      }
    },
    getConnectionStatus: async (signal): Promise<ConnectionStatus> => {
      try {
        await fetchJson('/api/v1/health', signal);
        return 'connected';
      } catch {
        return 'offline';
      }
    },
    isReadOnly: async (_runId, signal) => {
      const status = await fetchJson<{ readOnly?: boolean }>('/api/v1/workspace/status', signal);
      return Boolean(status.readOnly);
    },
  };
}

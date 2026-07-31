import {
  afterActionReportSchema,
  afterActionViewModelSchema,
  agentSessionDetailSchema,
  apiErrorEnvelopeSchema,
  graphSnapshotSchema,
  investigationDetailSchema,
  parseContract,
  replayCursorSchema,
  replayStateSchema,
  reportVersionSchema,
  riskScoresListResponseSchema,
  runScoreSchema,
  snapshotManifestSchema,
  stateDiffSchema,
} from '@aegis/contracts-ts';

import type {
  AegisApiClient,
  ConnectionStatus,
  ReplayQueryParams,
  RunGraphResult,
} from '@/lib/api/types';
import { apiFetch } from '@/lib/api/auth-fetch';
import { ApiClientError } from '@/lib/api/types';

function buildReplayQuery(params?: ReplayQueryParams): string {
  if (!params) {
    return '';
  }
  const search = new URLSearchParams();
  if (params.sequence != null) {
    search.set('sequence', String(params.sequence));
  }
  if (params.simTime) {
    search.set('simTime', params.simTime);
  }
  if (params.incidentId) {
    search.set('incidentId', params.incidentId);
  }
  if (params.preferSnapshot != null) {
    search.set('preferSnapshot', String(params.preferSnapshot));
  }
  const query = search.toString();
  return query ? `?${query}` : '';
}

async function fetchJson<T>(
  path: string,
  signal?: AbortSignal,
  parser?: (data: unknown) => T,
): Promise<T> {
  const response = await apiFetch(path, {
    signal,
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
      traceId: envelope.traceId ?? undefined,
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
    listAllIncidents: (signal) => fetchJson('/api/v1/incidents', signal),
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
    getAfterActionReport: (runId, signal) =>
      fetchJson(`/api/v1/runs/${runId}/after-action-report`, signal, (data) =>
        parseContract(afterActionReportSchema, data),
      ),
    listAfterActionReportVersions: async (runId, signal) => {
      const data = await fetchJson<unknown[]>(
        `/api/v1/runs/${runId}/after-action-report/versions`,
        signal,
      );
      return data.map((item) => parseContract(reportVersionSchema, item));
    },
    getAfterAction: (runId, signal) =>
      fetchJson(`/api/v1/runs/${runId}/after-action`, signal, (data) =>
        parseContract(afterActionViewModelSchema, data),
      ),
    getRunScore: (runId, signal) =>
      fetchJson(`/api/v1/runs/${runId}/score`, signal, (data) =>
        parseContract(runScoreSchema, data),
      ),
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
    getReplayState: (runId, params, signal) =>
      fetchJson(`/api/v1/replay/runs/${runId}/state${buildReplayQuery(params)}`, signal, (data) =>
        parseContract(replayStateSchema, data),
      ),
    getReplayCursor: (runId, params, signal) =>
      fetchJson(`/api/v1/replay/runs/${runId}/cursor${buildReplayQuery(params)}`, signal, (data) =>
        parseContract(replayCursorSchema, data),
      ),
    getReplayDiff: (runId, fromSequence, toSequence, signal) =>
      fetchJson(
        `/api/v1/replay/runs/${runId}/diff?fromSequence=${String(fromSequence)}&toSequence=${String(toSequence)}`,
        signal,
        (data) => parseContract(stateDiffSchema, data),
      ),
    listReplaySnapshots: async (runId, signal) => {
      const data = await fetchJson<unknown[]>(`/api/v1/replay/runs/${runId}/snapshots`, signal);
      return data.map((item) => parseContract(snapshotManifestSchema, item));
    },
  };
}

import type {
  AgentSessionDetailV1,
  AlertV1,
  AssetRiskScoreV1,
  GraphSnapshotV1,
  IncidentV1,
  InvestigationDetailV1,
  RunV1,
  ScenarioV1,
  ScenarioVersionV1,
} from '@aegis/contracts-ts';

export type {
  AgentSessionDetailV1,
  AlertV1,
  AssetRiskScoreV1,
  GraphSnapshotV1,
  IncidentV1,
  InvestigationDetailV1,
  RunV1,
  ScenarioV1,
  ScenarioVersionV1,
};

export type ConnectionStatus = 'connected' | 'reconnecting' | 'offline';

export interface RunGraphResult {
  snapshot: GraphSnapshotV1 | null;
  partial: boolean;
}

export interface FixtureProfile {
  id: string;
  connectionStatus: ConnectionStatus;
  readOnly: boolean;
  simulateLoadingMs: number;
  simulateError: boolean;
  emptyScenarios: boolean;
  omitGraphSnapshot: boolean;
}

export interface AegisApiClient {
  listScenarios(signal?: AbortSignal): Promise<ScenarioV1[]>;
  getScenario(scenarioId: string, signal?: AbortSignal): Promise<ScenarioV1>;
  listScenarioVersions(scenarioId: string, signal?: AbortSignal): Promise<ScenarioVersionV1[]>;
  getRun(runId: string, signal?: AbortSignal): Promise<RunV1>;
  listRuns(signal?: AbortSignal): Promise<RunV1[]>;
  listIncidents(runId: string, signal?: AbortSignal): Promise<IncidentV1[]>;
  getIncident(incidentId: string, signal?: AbortSignal): Promise<IncidentV1>;
  getInvestigationDetail(incidentId: string, signal?: AbortSignal): Promise<InvestigationDetailV1>;
  getAgentSession(sessionId: string, signal?: AbortSignal): Promise<AgentSessionDetailV1>;
  listAlerts(runId: string, signal?: AbortSignal): Promise<AlertV1[]>;
  listRiskScores(runId: string, signal?: AbortSignal): Promise<AssetRiskScoreV1[]>;
  getRunGraph(runId: string, signal?: AbortSignal): Promise<RunGraphResult>;
  getConnectionStatus(signal?: AbortSignal): Promise<ConnectionStatus>;
  isReadOnly(runId: string, signal?: AbortSignal): Promise<boolean>;
}

export class ApiClientError extends Error {
  readonly code: string;
  readonly status: number;
  readonly traceId?: string;

  constructor(options: { code: string; message: string; status: number; traceId?: string }) {
    super(options.message);
    this.name = 'ApiClientError';
    this.code = options.code;
    this.status = options.status;
    this.traceId = options.traceId;
  }
}

export function isNotFoundError(error: unknown): boolean {
  return error instanceof ApiClientError && error.status === 404;
}

import {
  alertSchema,
  graphSnapshotSchema,
  incidentSchema,
  parseContract,
  runSchema,
  scenarioSchema,
  scenarioVersionSchema,
} from '@aegis/contracts-ts';
import { z } from 'zod';

import {
  getAgentSessionFixture,
  getInvestigationDetailFixture,
} from '@/fixtures/investigation-fixture';
import {
  getReplayCursorFixture,
  getReplayDiffFixture,
  getReplayStateFixture,
  listReplaySnapshotsFixture,
} from '@/fixtures/replay-fixture';
import { getAfterActionReportFixture, getReportVersionsFixture } from '@/fixtures/report-fixture';
import shellDataset from '@/fixtures/shell-dataset.json';
import { FIXTURE_RISK_SCORES } from '@/fixtures/risk-scores-fixture';
import type {
  AegisApiClient,
  ConnectionStatus,
  FixtureProfile,
  RunGraphResult,
} from '@/lib/api/types';
import { ApiClientError } from '@/lib/api/types';
import { buildStressGraphSnapshot, STRESS_GRAPH_RUN_ID } from '@aegis/graph-domain';

const fixtureProfileSchema = z
  .object({
    id: z.string(),
    connectionStatus: z.enum(['connected', 'reconnecting', 'offline']),
    readOnly: z.boolean(),
    simulateLoadingMs: z.number().int().min(0),
    simulateError: z.boolean(),
    emptyScenarios: z.boolean(),
    omitGraphSnapshot: z.boolean(),
  })
  .strict();

const timelineMarkSchema = z
  .object({
    sequence: z.number().int(),
    label: z.string(),
    timestamp: z.string(),
    status: z.string(),
  })
  .strict();

export interface ShellDataset {
  schemaVersion: 1;
  profiles: Record<string, FixtureProfile>;
  scenarios: ReturnType<typeof scenarioSchema.parse>[];
  scenarioVersions: ReturnType<typeof scenarioVersionSchema.parse>[];
  runs: ReturnType<typeof runSchema.parse>[];
  incidents: ReturnType<typeof incidentSchema.parse>[];
  alerts: ReturnType<typeof alertSchema.parse>[];
  graphSnapshots: ReturnType<typeof graphSnapshotSchema.parse>[];
  timelineMarks: z.infer<typeof timelineMarkSchema>[];
}

export type TimelineMarkFixture = ShellDataset['timelineMarks'][number];

let validatedDataset: ShellDataset | null = null;

function validateShellDataset(raw: unknown): ShellDataset {
  const envelope = z
    .object({
      schemaVersion: z.literal(1),
      profiles: z.record(z.string(), fixtureProfileSchema),
      scenarios: z.array(z.unknown()),
      scenarioVersions: z.array(z.unknown()),
      runs: z.array(z.unknown()),
      incidents: z.array(z.unknown()),
      alerts: z.array(z.unknown()),
      graphSnapshots: z.array(z.unknown()),
      timelineMarks: z.array(timelineMarkSchema),
    })
    .strict()
    .parse(raw);

  return {
    schemaVersion: 1,
    profiles: envelope.profiles,
    scenarios: envelope.scenarios.map((item) => parseContract(scenarioSchema, item)),
    scenarioVersions: envelope.scenarioVersions.map((item) =>
      parseContract(scenarioVersionSchema, item),
    ),
    runs: envelope.runs.map((item) => parseContract(runSchema, item)),
    incidents: envelope.incidents.map((item) => parseContract(incidentSchema, item)),
    alerts: envelope.alerts.map((item) => parseContract(alertSchema, item)),
    graphSnapshots: envelope.graphSnapshots.map((item) => parseContract(graphSnapshotSchema, item)),
    timelineMarks: envelope.timelineMarks,
  };
}

export function loadShellDataset(): ShellDataset {
  if (validatedDataset) {
    return validatedDataset;
  }
  validatedDataset = validateShellDataset(shellDataset);
  return validatedDataset;
}

export function resetShellDatasetCache(): void {
  validatedDataset = null;
}

export interface FixtureProviderOptions {
  profileId?: string;
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  if (ms <= 0) {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(new DOMException('Aborted', 'AbortError'));
      },
      { once: true },
    );
  });
}

export function createFixtureProvider(options: FixtureProviderOptions = {}): AegisApiClient {
  const dataset = loadShellDataset();
  const profileId = options.profileId ?? 'default';
  const defaultProfile = dataset.profiles['default'];
  if (!defaultProfile) {
    throw new Error('Fixture dataset is missing the default profile');
  }
  const profile: FixtureProfile = dataset.profiles[profileId] ?? defaultProfile;

  async function applyProfile<T>(value: T, signal?: AbortSignal): Promise<T> {
    await delay(profile.simulateLoadingMs, signal);
    if (profile.simulateError) {
      throw new ApiClientError({
        code: 'FIXTURE_SIMULATED_ERROR',
        message: 'Simulated fixture error for shell development',
        status: 500,
      });
    }
    return value;
  }

  return {
    async listScenarios(signal) {
      const scenarios = profile.emptyScenarios ? [] : dataset.scenarios;
      return applyProfile(scenarios, signal);
    },

    async getScenario(scenarioId, signal) {
      const scenario = dataset.scenarios.find((item) => item.id === scenarioId);
      if (!scenario) {
        throw new ApiClientError({
          code: 'NOT_FOUND',
          message: `Scenario not found: ${scenarioId}`,
          status: 404,
        });
      }
      return applyProfile(scenario, signal);
    },

    async listScenarioVersions(scenarioId, signal) {
      const versions = dataset.scenarioVersions.filter((item) => item.scenarioId === scenarioId);
      return applyProfile(versions, signal);
    },

    async getRun(runId, signal) {
      const run = dataset.runs.find((item) => item.id === runId);
      if (!run) {
        if (
          runId === 'run_01ARZ3NDEKTSV4RRFFQ69G5FZ0' ||
          runId === 'run_01ARZ3NDEKTSV4RRFFQ69G5FZ1' ||
          runId === 'run_01ARZ3NDEKTSV4RRFFQ69G5FZ2'
        ) {
          return applyProfile(
            parseContract(runSchema, {
              schemaVersion: 1,
              id: runId,
              scenarioVersionId: 'scenario-version:v1.0.0-synthetic',
              seed: 1,
              status: 'failed',
              startedAt: '2026-06-30T02:00:00.000Z',
              simTime: '2026-01-01T18:00:00.000Z',
              revision: 1,
            }),
            signal,
          );
        }
        throw new ApiClientError({
          code: 'NOT_FOUND',
          message: `Run not found: ${runId}`,
          status: 404,
        });
      }
      return applyProfile(run, signal);
    },

    async listRuns(signal) {
      return applyProfile(dataset.runs, signal);
    },

    async listIncidents(runId, signal) {
      const incidents = dataset.incidents.filter((item) => item.runId === runId);
      return applyProfile(incidents, signal);
    },

    async getIncident(incidentId, signal) {
      const incident = dataset.incidents.find((item) => item.id === incidentId);
      if (!incident) {
        throw new ApiClientError({
          code: 'NOT_FOUND',
          message: `Incident not found: ${incidentId}`,
          status: 404,
        });
      }
      return applyProfile(incident, signal);
    },

    async getInvestigationDetail(incidentId, signal) {
      const detail = getInvestigationDetailFixture(incidentId);
      if (!detail) {
        throw new ApiClientError({
          code: 'NOT_FOUND',
          message: `Investigation not found for incident: ${incidentId}`,
          status: 404,
        });
      }
      return applyProfile(detail, signal);
    },

    async getAgentSession(sessionId, signal) {
      const session = getAgentSessionFixture(sessionId);
      if (!session) {
        throw new ApiClientError({
          code: 'NOT_FOUND',
          message: `Agent session not found: ${sessionId}`,
          status: 404,
        });
      }
      return applyProfile(session, signal);
    },

    async listAlerts(runId, signal) {
      const alerts = dataset.alerts.filter((item) => item.runId === runId);
      return applyProfile(alerts, signal);
    },

    async listRiskScores(runId, signal) {
      const scores = FIXTURE_RISK_SCORES.filter((item) => item.runId === runId);
      return applyProfile(scores, signal);
    },

    async getRunGraph(runId, signal) {
      if (profile.omitGraphSnapshot) {
        return applyProfile({ snapshot: null, partial: true } satisfies RunGraphResult, signal);
      }
      if (runId === STRESS_GRAPH_RUN_ID) {
        return applyProfile(
          {
            snapshot: buildStressGraphSnapshot(),
            partial: false,
          } satisfies RunGraphResult,
          signal,
        );
      }
      const snapshot = dataset.graphSnapshots.find((item) => item.runId === runId);
      if (!snapshot) {
        return applyProfile({ snapshot: null, partial: true }, signal);
      }
      return applyProfile({ snapshot, partial: false } satisfies RunGraphResult, signal);
    },

    async getAfterActionReport(runId, signal) {
      const report = getAfterActionReportFixture(runId);
      if (!report) {
        throw new ApiClientError({
          code: 'REPORT_NOT_FOUND',
          message: `No report found for run ${runId}`,
          status: 404,
        });
      }
      return applyProfile(report, signal);
    },

    async listAfterActionReportVersions(runId, signal) {
      return applyProfile(getReportVersionsFixture(runId), signal);
    },

    async getConnectionStatus(signal) {
      await delay(profile.simulateLoadingMs, signal);
      return profile.connectionStatus satisfies ConnectionStatus;
    },

    async isReadOnly(runId, signal) {
      await this.getRun(runId, signal);
      return profile.readOnly;
    },

    async getReplayState(runId, params, signal) {
      try {
        const state = getReplayStateFixture(runId, params);
        return await applyProfile(state, signal);
      } catch (error) {
        const code =
          error && typeof error === 'object' && 'code' in error
            ? String((error as { code: string }).code)
            : 'REPLAY_NOT_FOUND';
        const status =
          error && typeof error === 'object' && 'status' in error
            ? Number((error as { status: number }).status)
            : 404;
        throw new ApiClientError({
          code,
          message: error instanceof Error ? error.message : 'Replay state unavailable',
          status,
        });
      }
    },

    async getReplayCursor(runId, params, signal) {
      try {
        const cursor = getReplayCursorFixture(runId, params);
        return await applyProfile(cursor, signal);
      } catch (error) {
        const code =
          error && typeof error === 'object' && 'code' in error
            ? String((error as { code: string }).code)
            : 'REPLAY_NOT_FOUND';
        const status =
          error && typeof error === 'object' && 'status' in error
            ? Number((error as { status: number }).status)
            : 404;
        throw new ApiClientError({
          code,
          message: error instanceof Error ? error.message : 'Replay cursor unavailable',
          status,
        });
      }
    },

    async getReplayDiff(runId, fromSequence, toSequence, signal) {
      try {
        const diff = getReplayDiffFixture(runId, fromSequence, toSequence);
        return await applyProfile(diff, signal);
      } catch (error) {
        throw new ApiClientError({
          code: 'REPLAY_VALIDATION_FAILED',
          message: error instanceof Error ? error.message : 'Replay diff unavailable',
          status: 400,
        });
      }
    },

    async listReplaySnapshots(runId, signal) {
      return await applyProfile(listReplaySnapshotsFixture(runId), signal);
    },
  };
}

export function getTimelineMarks(): TimelineMarkFixture[] {
  return loadShellDataset().timelineMarks;
}

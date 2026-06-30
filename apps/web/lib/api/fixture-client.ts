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

import shellDataset from '@/fixtures/shell-dataset.json';
import type {
  AegisApiClient,
  ConnectionStatus,
  FixtureProfile,
  RunGraphResult,
} from '@/lib/api/types';
import { ApiClientError } from '@/lib/api/types';

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

    async listAlerts(runId, signal) {
      const alerts = dataset.alerts.filter((item) => item.runId === runId);
      return applyProfile(alerts, signal);
    },

    async getRunGraph(runId, signal) {
      if (profile.omitGraphSnapshot) {
        return applyProfile({ snapshot: null, partial: true } satisfies RunGraphResult, signal);
      }
      const snapshot = dataset.graphSnapshots.find((item) => item.runId === runId);
      if (!snapshot) {
        return applyProfile({ snapshot: null, partial: true }, signal);
      }
      return applyProfile({ snapshot, partial: false } satisfies RunGraphResult, signal);
    },

    async getConnectionStatus(signal) {
      await delay(profile.simulateLoadingMs, signal);
      return profile.connectionStatus satisfies ConnectionStatus;
    },

    async isReadOnly(runId, signal) {
      await this.getRun(runId, signal);
      return profile.readOnly;
    },
  };
}

export function getTimelineMarks(): TimelineMarkFixture[] {
  return loadShellDataset().timelineMarks;
}

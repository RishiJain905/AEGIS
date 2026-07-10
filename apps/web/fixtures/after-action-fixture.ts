import {
  afterActionViewModelSchema,
  parseContract,
  runScoreSchema,
  type AfterActionViewModelV1,
  type RunScoreV1,
} from '@aegis/contracts-ts';

import afterActionFixtureJson from '@/fixtures/after-action-fixture.json';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

export function getAfterActionFixture(runId: string = RUN_ID): AfterActionViewModelV1 {
  const payload = {
    ...afterActionFixtureJson,
    runId,
    score: {
      ...afterActionFixtureJson.score,
      runId,
    },
  };
  return parseContract(afterActionViewModelSchema, payload);
}

export function getRunScoreFixture(runId: string = RUN_ID): RunScoreV1 {
  return getAfterActionFixture(runId).score;
}

export function getScoreExportFixture(runId: string = RUN_ID): {
  metadata: Record<string, string>;
  body: string;
} {
  const score = getRunScoreFixture(runId);
  return {
    metadata: {
      scoreId: score.scoreId,
      scenarioVersion: score.provenance.scenarioVersion,
      rubricVersion: score.provenance.rubricVersion,
      gradingEngineVersion: score.provenance.gradingEngineVersion,
      integrityChecksum: score.provenance.integrityChecksum,
      fingerprint: score.provenance.fingerprint,
    },
    body: JSON.stringify(score, null, 2),
  };
}

export { runScoreSchema };

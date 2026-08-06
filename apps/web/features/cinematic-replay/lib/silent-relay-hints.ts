import type { PresentationHintV1 } from '@aegis/contracts-ts';

/**
 * Safe Silent Relay presentation hints.
 * Never reveal hidden causes; captions are emphasis-only over known sequences.
 */
export const SILENT_RELAY_PRESENTATION_HINTS: PresentationHintV1[] = [
  {
    schemaVersion: 1,
    id: 'hint_baseline_overview',
    scenarioId: 'scenario:operation-silent-relay',
    kind: 'chapter_anchor',
    sequence: 0,
    entityIds: [],
    caption: 'Establish the operational graph under baseline conditions.',
    chapterId: 'chapter-baseline',
    requiresEvidenceIds: [],
    revealsHiddenCause: false,
    hiddenCauseId: null,
  },
  {
    schemaVersion: 1,
    id: 'hint_early_risk',
    scenarioId: 'scenario:operation-silent-relay',
    kind: 'emphasis',
    sequence: 40,
    entityIds: ['asset:svc-api-gateway'],
    caption: 'Early risk drift appears around the API gateway.',
    chapterId: 'chapter-early-signals',
    requiresEvidenceIds: [],
    revealsHiddenCause: false,
    hiddenCauseId: null,
  },
  {
    schemaVersion: 1,
    id: 'hint_incident_origin',
    scenarioId: 'scenario:operation-silent-relay',
    kind: 'emphasis',
    sequence: 120,
    entityIds: ['asset:svc-api-gateway'],
    caption: 'Focus on the first major anomaly around the API gateway.',
    chapterId: 'chapter-escalation',
    requiresEvidenceIds: [],
    revealsHiddenCause: false,
    hiddenCauseId: null,
  },
  {
    schemaVersion: 1,
    id: 'hint_evidence_workstation',
    scenarioId: 'scenario:operation-silent-relay',
    kind: 'emphasis',
    sequence: 180,
    entityIds: ['asset:device-workstation-01'],
    caption: 'Related evidence points at the affected workstation.',
    chapterId: 'chapter-escalation',
    requiresEvidenceIds: ['evidence:evd_synthetic_001'],
    revealsHiddenCause: false,
    hiddenCauseId: null,
  },
  {
    schemaVersion: 1,
    id: 'hint_agent_trace',
    scenarioId: 'scenario:operation-silent-relay',
    kind: 'caption',
    sequence: 250,
    entityIds: ['asset:device-workstation-01'],
    caption: 'TRACE investigation activity concentrates on related assets.',
    chapterId: 'chapter-decision',
    requiresEvidenceIds: [],
    revealsHiddenCause: false,
    hiddenCauseId: null,
  },
];

// A run belongs to Silent Relay when its scenario-version id carries this marker (e.g.
// `scenario-version:1.0.0-silent-relay`). Matching the marker rather than a literal id
// keeps the match stable across scenario version bumps — the same convention the tutorial
// controller uses to recognise its own runs.
const SILENT_RELAY_SCENARIO_MARKER = 'silent-relay';

/**
 * The presentation hints that legitimately describe `scenarioVersionId`'s run.
 *
 * The hints above name Silent Relay's estate outright — its API gateway, its workstation —
 * and carry `scenarioId: 'scenario:operation-silent-relay'` to say so. Nothing checked that
 * field: the director handed this array to the planner for every run, so a training run
 * scrubbed in cinematic mode was captioned "Early risk drift appears around the API
 * gateway" over a graph that has no such asset. A hint set only applies to the scenario it
 * was authored for; any other run plans from its own replay state, which is what the
 * planner does when it is given no hints at all.
 */
export function presentationHintsForRun(
  scenarioVersionId: string | null | undefined,
): PresentationHintV1[] {
  if (scenarioVersionId?.includes(SILENT_RELAY_SCENARIO_MARKER) !== true) {
    return [];
  }
  return SILENT_RELAY_PRESENTATION_HINTS;
}

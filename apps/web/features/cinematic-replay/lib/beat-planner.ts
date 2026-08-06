import {
  parseContract,
  cinematicPlanSchema,
  type CameraDirectiveV1,
  type CinematicBeatKind,
  type CinematicBeatV1,
  type CinematicChapterV1,
  type CinematicPlanV1,
  type PresentationHintV1,
  type ReplayStateV1,
} from '@aegis/contracts-ts';

import { filterSafePresentationHints } from './hint-gating';

export interface ChapterTemplate {
  id: string;
  title: string;
  summary: string;
  fromSequence: number;
  toSequence: number;
  order: number;
}

/**
 * Default chapter scaffolding — labels over sequences, not a second timeline.
 *
 * Applied to every run the planner sees, so the titles and summaries describe the arc of a
 * defensive engagement in general and never assert a fact about one scenario's estate. The
 * baseline summary used to count "eight organizational zones", which is Silent Relay's
 * topology stated over whichever run was actually being replayed.
 */
export const SILENT_RELAY_CHAPTER_TEMPLATES: readonly ChapterTemplate[] = [
  {
    id: 'chapter-baseline',
    title: 'Baseline operations',
    summary: 'Normal telemetry across the organizational zones.',
    fromSequence: 0,
    toSequence: 39,
    order: 0,
  },
  {
    id: 'chapter-early-signals',
    title: 'Early signals',
    summary: 'Overlapping clues and distractors emerge.',
    fromSequence: 40,
    toSequence: 119,
    order: 1,
  },
  {
    id: 'chapter-escalation',
    title: 'Escalation',
    summary: 'Cause-specific evidence crosses detection thresholds.',
    fromSequence: 120,
    toSequence: 249,
    order: 2,
  },
  {
    id: 'chapter-decision',
    title: 'Decision point',
    summary: 'Operator selects containment, investigation, or remediation.',
    fromSequence: 250,
    toSequence: 399,
    order: 3,
  },
  {
    id: 'chapter-consequences',
    title: 'Consequences',
    summary: 'Asset status and relationship confidence reflect the chosen path.',
    fromSequence: 400,
    toSequence: Number.MAX_SAFE_INTEGER,
    order: 4,
  },
] as const;

function chapterForSequence(
  sequence: number,
  templates: readonly ChapterTemplate[],
): ChapterTemplate {
  const match = templates.find(
    (chapter) => sequence >= chapter.fromSequence && sequence <= chapter.toSequence,
  );
  if (match) {
    return match;
  }
  const fallback = templates[templates.length - 1];
  if (!fallback) {
    throw new Error('Chapter templates must not be empty');
  }
  return fallback;
}

function defaultBookmark(kind: CameraDirectiveV1['kind']): CameraDirectiveV1['bookmark'] {
  switch (kind) {
    case 'establishing':
    case 'overview':
      return {
        position: { x: 0, y: 180, z: 320 },
        target: { x: 0, y: 0, z: 0 },
        fov: 50,
      };
    case 'entity_focus':
    case 'agent_focus':
    case 'approval':
      return {
        position: { x: 40, y: 140, z: 240 },
        target: { x: 0, y: 0, z: 0 },
        fov: 46,
      };
    case 'path_trace':
      return {
        position: { x: 80, y: 120, z: 260 },
        target: { x: 20, y: 0, z: 0 },
        fov: 48,
      };
    case 'consequence':
      return {
        position: { x: -40, y: 160, z: 300 },
        target: { x: 0, y: 0, z: 0 },
        fov: 52,
      };
    default: {
      const _exhaustive: never = kind;
      return _exhaustive;
    }
  }
}

function makeDirective(
  id: string,
  kind: CameraDirectiveV1['kind'],
  focusEntityIds: string[],
  pathEntityIds: string[] = [],
): CameraDirectiveV1 {
  return {
    schemaVersion: 1,
    id,
    kind,
    focusEntityIds,
    pathEntityIds,
    bookmark: defaultBookmark(kind),
    transitionMs: kind === 'establishing' || kind === 'overview' ? 0 : 800,
    reducedMotionJump: true,
  };
}

function makeBeat(input: {
  id: string;
  chapterId: string;
  kind: CinematicBeatKind;
  sequence: number;
  caption: string;
  entityIds: string[];
  pathEntityIds?: string[];
  cameraDirectiveId: string;
  runId: string;
  simTime?: string | null;
  incidentId?: string | null;
  stateDigest?: string | null;
  source: CinematicBeatV1['provenance']['source'];
  priority: number;
  tieBreaker: number;
}): CinematicBeatV1 {
  return {
    schemaVersion: 1,
    id: input.id,
    chapterId: input.chapterId,
    kind: input.kind,
    sequence: input.sequence,
    simTime: input.simTime ?? null,
    caption: input.caption,
    entityIds: input.entityIds,
    pathEntityIds: input.pathEntityIds ?? [],
    cameraDirectiveId: input.cameraDirectiveId,
    provenance: {
      schemaVersion: 1,
      runId: input.runId,
      sequence: input.sequence,
      simTime: input.simTime ?? null,
      entityIds: input.entityIds,
      incidentId: input.incidentId ?? null,
      source: input.source,
      stateDigest: input.stateDigest ?? null,
    },
    priority: input.priority,
    tieBreaker: input.tieBreaker,
  };
}

function knownGraphEntityIds(state: ReplayStateV1): Set<string> {
  const ids = new Set<string>();
  for (const node of state.graph?.nodes ?? []) {
    ids.add(node.id);
  }
  return ids;
}

function resolveExistingEntities(
  candidates: string[],
  known: Set<string>,
  warnings: string[],
  beatId: string,
): string[] {
  const existing: string[] = [];
  for (const id of candidates) {
    if (known.size === 0 || known.has(id)) {
      existing.push(id);
    } else {
      warnings.push(`Missing entity reference ${id} for beat ${beatId}; skipped.`);
    }
  }
  return existing;
}

export interface PlanCinematicBeatsOptions {
  state: ReplayStateV1;
  hints?: PresentationHintV1[];
  chapterTemplates?: readonly ChapterTemplate[];
}

/**
 * Deterministic cinematic plan from authoritative ReplayStateV1.
 * Never reorders chronology for drama; never invents domain entities.
 */
export function planCinematicBeats(options: PlanCinematicBeatsOptions): CinematicPlanV1 {
  const { state } = options;
  const templates = options.chapterTemplates ?? SILENT_RELAY_CHAPTER_TEMPLATES;
  const warnings: string[] = [];
  const known = knownGraphEntityIds(state);
  const safeHints = filterSafePresentationHints(options.hints ?? [], state, warnings);

  const maxSequence = state.cursor.sequence;
  const chapters: CinematicChapterV1[] = templates
    .filter((template) => template.fromSequence <= maxSequence)
    .map((template) => ({
      schemaVersion: 1,
      id: template.id,
      title: template.title,
      summary: template.summary,
      fromSequence: template.fromSequence,
      toSequence: Math.min(template.toSequence, maxSequence),
      beatIds: [],
      order: template.order,
    }));

  if (chapters.length === 0) {
    chapters.push({
      schemaVersion: 1,
      id: 'chapter-baseline',
      title: 'Baseline operations',
      summary: 'Normal telemetry across organizational zones.',
      fromSequence: 0,
      toSequence: maxSequence,
      beatIds: [],
      order: 0,
    });
  }

  const beats: CinematicBeatV1[] = [];
  const directives: CameraDirectiveV1[] = [];
  let tie = 0;

  const pushBeat = (beat: CinematicBeatV1, directive: CameraDirectiveV1): void => {
    directives.push(directive);
    beats.push(beat);
  };

  // Establishing overview at sequence 0
  {
    const chapter = chapterForSequence(0, templates);
    const camId = 'cam_establishing_001';
    pushBeat(
      makeBeat({
        id: 'beat_establishing_001',
        chapterId: chapter.id,
        kind: 'establishing',
        sequence: 0,
        // Every run opens on this beat, so the caption cannot name a scenario — it read
        // "Operation Silent Relay begins…" over a training run's own graph.
        caption: 'The operation begins under normal baseline conditions.',
        entityIds: [],
        cameraDirectiveId: camId,
        runId: state.runId,
        simTime: null,
        source: 'default_planner',
        stateDigest: state.stateDigest,
        priority: 0,
        tieBreaker: tie++,
      }),
      makeDirective(camId, 'establishing', []),
    );
  }

  // Risk change from riskScores / early telemetry
  if (state.riskScores.length > 0 || state.auditEvents.some((e) => e.sequence === 40)) {
    const sequence = 40;
    if (sequence <= maxSequence) {
      const chapter = chapterForSequence(sequence, templates);
      const entityIds = resolveExistingEntities(
        state.riskScores.map((r) => r.assetId).slice(0, 3),
        known,
        warnings,
        'beat_risk_change_001',
      );
      const camId = 'cam_risk_change_001';
      pushBeat(
        makeBeat({
          id: 'beat_risk_change_001',
          chapterId: chapter.id,
          kind: 'risk_change',
          sequence,
          caption: 'Risk and telemetry signals begin to diverge from baseline.',
          entityIds,
          cameraDirectiveId: camId,
          runId: state.runId,
          source: 'replay_state',
          stateDigest: state.stateDigest,
          priority: 20,
          tieBreaker: tie++,
        }),
        makeDirective(camId, entityIds.length > 0 ? 'entity_focus' : 'overview', entityIds),
      );
    }
  }

  // Incident origin
  const incident = state.incidents[0];
  if (incident) {
    const sequence =
      state.auditEvents.find((e) => e.eventType === 'incident.opened')?.sequence ?? 120;
    if (sequence <= maxSequence) {
      const chapter = chapterForSequence(sequence, templates);
      const focusFromHints = safeHints
        .filter((h) => h.sequence === sequence || h.chapterId === chapter.id)
        .flatMap((h) => h.entityIds);
      // Focus only where a hint actually points. The fallback here was a literal
      // `asset:svc-api-gateway` — Silent Relay's gateway, framed as the origin of whatever
      // incident this run opened, on any scenario and regardless of the real origin. With
      // no hint there is nothing truthful to focus on, so the camera pulls back instead.
      const entityIds = resolveExistingEntities(
        focusFromHints,
        known,
        warnings,
        'beat_incident_origin_001',
      );
      const camId = 'cam_incident_origin_001';
      const hintCaption = safeHints.find((h) => h.sequence === sequence)?.caption;
      pushBeat(
        makeBeat({
          id: 'beat_incident_origin_001',
          chapterId: chapter.id,
          kind: 'incident_origin',
          sequence,
          caption:
            hintCaption ?? `${incident.title} opens the primary incident (${incident.state}).`,
          entityIds,
          cameraDirectiveId: camId,
          runId: state.runId,
          incidentId: incident.id,
          source: hintCaption ? 'presentation_hint' : 'replay_state',
          stateDigest: state.stateDigest,
          priority: 10,
          tieBreaker: tie++,
        }),
        makeDirective(camId, entityIds.length > 0 ? 'entity_focus' : 'overview', entityIds),
      );
    }
  }

  // Evidence focus
  const evidence = state.evidence[0];
  if (evidence) {
    const sequence =
      state.auditEvents.find((e) => e.eventType === 'evidence.attached')?.sequence ?? 180;
    if (sequence <= maxSequence) {
      const chapter = chapterForSequence(sequence, templates);
      const entityIds = resolveExistingEntities(
        evidence.assetId ? [evidence.assetId] : [],
        known,
        warnings,
        'beat_evidence_focus_001',
      );
      // The path traced here has to be one the run actually contains. Seeding it with
      // `asset:svc-api-gateway` drew a line from Silent Relay's gateway to this run's
      // evidence asset, asserting a relationship nothing in the replay state supports.
      // One endpoint is not a path, and `makeDirective` below already falls back to
      // `entity_focus` when fewer than two resolve.
      const pathCandidates = evidence.assetId ? [evidence.assetId] : [];
      const pathEntityIds = resolveExistingEntities(
        pathCandidates,
        known,
        warnings,
        'beat_evidence_focus_001_path',
      );
      const camId = 'cam_evidence_focus_001';
      pushBeat(
        makeBeat({
          id: 'beat_evidence_focus_001',
          chapterId: chapter.id,
          kind: 'evidence_focus',
          sequence,
          caption: evidence.summary,
          entityIds,
          pathEntityIds,
          cameraDirectiveId: camId,
          runId: state.runId,
          incidentId: state.incidents[0]?.id ?? null,
          source: 'replay_state',
          stateDigest: state.stateDigest,
          priority: 15,
          tieBreaker: tie++,
        }),
        makeDirective(
          camId,
          pathEntityIds.length >= 2 ? 'path_trace' : 'entity_focus',
          entityIds,
          pathEntityIds,
        ),
      );
    }
  }

  // Agent investigation
  const session = state.agentSessions[0];
  if (session) {
    const sequence =
      state.auditEvents.find((e) => e.eventType === 'agent.session.started')?.sequence ?? 250;
    if (sequence <= maxSequence) {
      const chapter = chapterForSequence(sequence, templates);
      const evidenceAsset = state.evidence[0]?.assetId;
      const entityIds = resolveExistingEntities(
        evidenceAsset ? [evidenceAsset] : [],
        known,
        warnings,
        'beat_agent_investigation_001',
      );
      const camId = 'cam_agent_investigation_001';
      pushBeat(
        makeBeat({
          id: 'beat_agent_investigation_001',
          chapterId: chapter.id,
          kind: 'agent_investigation',
          sequence,
          caption: `${session.role} agent session ${session.state} — investigation activity.`,
          entityIds,
          cameraDirectiveId: camId,
          runId: state.runId,
          incidentId: session.incidentId,
          source: 'replay_state',
          stateDigest: state.stateDigest,
          priority: 25,
          tieBreaker: tie++,
        }),
        makeDirective(camId, 'agent_focus', entityIds),
      );
    }
  }

  // Proposal
  const proposal = state.proposals[0];
  if (proposal) {
    const sequence =
      state.auditEvents.find((e) => e.eventType === 'proposal.submitted')?.sequence ?? 320;
    if (sequence <= maxSequence) {
      const chapter = chapterForSequence(sequence, templates);
      const entityIds = resolveExistingEntities(
        proposal.targetAssetId ? [proposal.targetAssetId] : [],
        known,
        warnings,
        'beat_proposal_focus_001',
      );
      const camId = 'cam_proposal_focus_001';
      pushBeat(
        makeBeat({
          id: 'beat_proposal_focus_001',
          chapterId: chapter.id,
          kind: 'proposal_focus',
          sequence,
          caption: `Proposal ${proposal.command} (${proposal.status}): ${proposal.rationale}`,
          entityIds,
          cameraDirectiveId: camId,
          runId: state.runId,
          incidentId: proposal.incidentId,
          source: 'replay_state',
          stateDigest: state.stateDigest,
          priority: 30,
          tieBreaker: tie++,
        }),
        makeDirective(camId, 'entity_focus', entityIds),
      );
    }
  }

  // Approval
  const approval = state.approvals[0];
  if (approval) {
    const sequence =
      state.auditEvents.find((e) => e.eventType === 'approval.decided')?.sequence ?? 400;
    if (sequence <= maxSequence) {
      const chapter = chapterForSequence(sequence, templates);
      const linkedProposal = state.proposals.find((p) => p.id === approval.proposalId);
      const entityIds = resolveExistingEntities(
        linkedProposal?.targetAssetId ? [linkedProposal.targetAssetId] : [],
        known,
        warnings,
        'beat_approval_moment_001',
      );
      const camId = 'cam_approval_moment_001';
      pushBeat(
        makeBeat({
          id: 'beat_approval_moment_001',
          chapterId: chapter.id,
          kind: 'approval_moment',
          sequence,
          caption: `Operator ${approval.decision} proposal ${approval.proposalId}.`,
          entityIds,
          cameraDirectiveId: camId,
          runId: state.runId,
          incidentId: linkedProposal?.incidentId ?? state.incidents[0]?.id ?? null,
          source: 'replay_state',
          stateDigest: state.stateDigest,
          priority: 35,
          tieBreaker: tie++,
        }),
        makeDirective(camId, 'approval', entityIds),
      );
    }
  }

  // Consequence / executed action
  if (state.executedActions.length > 0) {
    const sequence =
      state.auditEvents.find((e) => e.eventType === 'action.executed')?.sequence ?? 500;
    if (sequence <= maxSequence) {
      const chapter = chapterForSequence(sequence, templates);
      const consequenceProposal = state.proposals[0];
      const entityIds = resolveExistingEntities(
        consequenceProposal?.targetAssetId ? [consequenceProposal.targetAssetId] : [],
        known,
        warnings,
        'beat_consequence_reveal_001',
      );
      const camId = 'cam_consequence_reveal_001';
      pushBeat(
        makeBeat({
          id: 'beat_consequence_reveal_001',
          chapterId: chapter.id,
          kind: 'consequence_reveal',
          sequence,
          caption: 'Authorized action executed — asset status and risk reflect consequences.',
          entityIds,
          cameraDirectiveId: camId,
          runId: state.runId,
          incidentId: state.incidents[0]?.id ?? null,
          source: 'replay_state',
          stateDigest: state.stateDigest,
          priority: 40,
          tieBreaker: tie++,
        }),
        makeDirective(camId, 'consequence', entityIds),
      );
    }
  }

  // Report focus
  const report = state.reports[0];
  if (report) {
    const sequence = maxSequence;
    const chapter = chapterForSequence(sequence, templates);
    const camId = 'cam_report_focus_001';
    pushBeat(
      makeBeat({
        id: 'beat_report_focus_001',
        chapterId: chapter.id,
        kind: 'report_focus',
        sequence,
        caption: `After-action report ${report.reportId} (${report.status}).`,
        entityIds: [],
        cameraDirectiveId: camId,
        runId: state.runId,
        incidentId: report.incidentId ?? null,
        source: 'replay_state',
        stateDigest: state.stateDigest,
        priority: 50,
        tieBreaker: tie++,
      }),
      makeDirective(camId, 'overview', []),
    );
  }

  // Final overview
  {
    const sequence = maxSequence;
    const chapter = chapterForSequence(sequence, templates);
    const camId = 'cam_overview_final_001';
    pushBeat(
      makeBeat({
        id: 'beat_overview_final_001',
        chapterId: chapter.id,
        kind: 'overview',
        sequence,
        caption: 'Cinematic overview of the reconstructed historical run state.',
        entityIds: [],
        cameraDirectiveId: camId,
        runId: state.runId,
        incidentId: state.incidents[0]?.id ?? null,
        source: 'default_planner',
        stateDigest: state.stateDigest,
        priority: 1000,
        tieBreaker: tie++,
      }),
      makeDirective(camId, 'overview', []),
    );
  }

  // Deterministic ordering: sequence, priority, tieBreaker
  beats.sort((a, b) => {
    if (a.sequence !== b.sequence) {
      return a.sequence - b.sequence;
    }
    if (a.priority !== b.priority) {
      return a.priority - b.priority;
    }
    return a.tieBreaker - b.tieBreaker;
  });

  for (const chapter of chapters) {
    chapter.beatIds = beats.filter((b) => b.chapterId === chapter.id).map((b) => b.id);
  }

  // Drop empty chapters that somehow have no beats and no overlap
  const nonEmptyChapters = chapters.filter((c) => c.beatIds.length > 0);
  const planChapters = nonEmptyChapters.length > 0 ? nonEmptyChapters : chapters;

  return parseContract(cinematicPlanSchema, {
    schemaVersion: 1,
    runId: state.runId,
    chapters: planChapters,
    beats,
    cameraDirectives: directives,
    warnings,
  });
}

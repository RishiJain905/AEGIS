import { describe, expect, it } from 'vitest';

import { getReplayStateFixture } from '@/fixtures/replay-fixture';
import { planCinematicBeats } from '@/features/cinematic-replay/lib/beat-planner';
import { filterSafePresentationHints } from '@/features/cinematic-replay/lib/hint-gating';
import {
  presentationHintsForRun,
  SILENT_RELAY_PRESENTATION_HINTS,
} from '@/features/cinematic-replay/lib/silent-relay-hints';
import type { PresentationHintV1 } from '@aegis/contracts-ts';

describe('cinematic beat planner', () => {
  it('builds coherent Silent Relay chapters from authoritative replay state', () => {
    const state = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 500 });
    const plan = planCinematicBeats({
      state,
      hints: SILENT_RELAY_PRESENTATION_HINTS,
    });

    expect(plan.runId).toBe(state.runId);
    expect(plan.chapters.length).toBeGreaterThanOrEqual(4);
    expect(plan.beats.length).toBeGreaterThanOrEqual(6);
    expect(plan.beats.map((b) => b.sequence)).toEqual(
      [...plan.beats]
        .sort((a, b) => a.sequence - b.sequence || a.priority - b.priority)
        .map((b) => b.sequence),
    );

    const kinds = new Set(plan.beats.map((b) => b.kind));
    expect(kinds.has('establishing')).toBe(true);
    expect(kinds.has('incident_origin')).toBe(true);
    expect(kinds.has('evidence_focus')).toBe(true);
    expect(kinds.has('agent_investigation')).toBe(true);
    expect(kinds.has('approval_moment')).toBe(true);
    expect(kinds.has('overview')).toBe(true);
  });

  it('links every beat to authoritative cursor/entity provenance', () => {
    const state = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 500 });
    const plan = planCinematicBeats({ state });
    for (const beat of plan.beats) {
      expect(beat.provenance.runId).toBe(state.runId);
      expect(beat.provenance.sequence).toBe(beat.sequence);
      expect(beat.provenance.source).toMatch(/replay_state|presentation_hint|default_planner/);
      expect(beat.cameraDirectiveId.length).toBeGreaterThan(0);
      expect(plan.cameraDirectives.some((d) => d.id === beat.cameraDirectiveId)).toBe(true);
    }
  });

  it('is deterministic for the same replay state', () => {
    const state = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 500 });
    const a = planCinematicBeats({ state, hints: SILENT_RELAY_PRESENTATION_HINTS });
    const b = planCinematicBeats({ state, hints: SILENT_RELAY_PRESENTATION_HINTS });
    expect(a.beats.map((beat) => beat.id)).toEqual(b.beats.map((beat) => beat.id));
    expect(a.chapters.map((chapter) => chapter.id)).toEqual(
      b.chapters.map((chapter) => chapter.id),
    );
  });

  it('skips missing entity references without inventing nodes', () => {
    const state = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 500 });
    const hints: PresentationHintV1[] = [
      {
        schemaVersion: 1,
        id: 'hint_missing',
        scenarioId: 'scenario:operation-silent-relay',
        kind: 'emphasis',
        sequence: 120,
        entityIds: ['asset:does-not-exist'],
        caption: 'Should warn',
        chapterId: 'chapter-escalation',
        requiresEvidenceIds: [],
        revealsHiddenCause: false,
        hiddenCauseId: null,
      },
    ];
    const plan = planCinematicBeats({ state, hints });
    expect(plan.warnings.some((w) => w.includes('asset:does-not-exist'))).toBe(true);
    const incidentBeat = plan.beats.find((b) => b.id === 'beat_incident_origin_001');
    expect(incidentBeat?.entityIds.includes('asset:does-not-exist')).toBe(false);
  });
});

describe('scenario-scoped presentation hints', () => {
  it('offers the Silent Relay hints only to a Silent Relay run', () => {
    expect(presentationHintsForRun('scenario-version:1.0.0-silent-relay')).toEqual(
      SILENT_RELAY_PRESENTATION_HINTS,
    );
    // The hints name Silent Relay's own assets, so no other scenario may borrow them.
    expect(presentationHintsForRun('scenario-version:1.0.0-synthetic-training')).toEqual([]);
    expect(presentationHintsForRun('scenario-version:unknown')).toEqual([]);
    expect(presentationHintsForRun(null)).toEqual([]);
    expect(presentationHintsForRun(undefined)).toEqual([]);
  });

  it('narrates an unhinted run from its own state, naming no scenario and no foreign asset', () => {
    const state = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 500 });
    const plan = planCinematicBeats({ state });

    const establishing = plan.beats.find((beat) => beat.kind === 'establishing');
    expect(establishing?.caption).not.toMatch(/Silent Relay/i);

    // Focus used to fall back to Silent Relay's `asset:svc-api-gateway` whenever no hint
    // named an entity; with no hints there is nothing truthful to point the camera at.
    const incidentBeat = plan.beats.find((beat) => beat.id === 'beat_incident_origin_001');
    expect(incidentBeat?.entityIds).toEqual([]);
    const incidentDirective = plan.cameraDirectives.find(
      (directive) => directive.id === incidentBeat?.cameraDirectiveId,
    );
    expect(incidentDirective?.kind).toBe('overview');

    // The evidence path traced from that same hardcoded gateway to the run's evidence
    // asset; it may now only contain entities the run itself supplied.
    const evidenceBeat = plan.beats.find((beat) => beat.id === 'beat_evidence_focus_001');
    const evidenceAssetId = state.evidence[0]?.assetId ?? null;
    for (const entityId of evidenceBeat?.pathEntityIds ?? []) {
      expect(entityId).toBe(evidenceAssetId);
    }
  });
});

describe('presentation hint gating', () => {
  it('blocks hidden-cause reveals and defers hints until evidence exists', () => {
    const early = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 40 });
    const warnings: string[] = [];
    const unsafe = {
      schemaVersion: 1,
      id: 'hint_unsafe',
      scenarioId: 'scenario:operation-silent-relay',
      kind: 'emphasis',
      sequence: 40,
      entityIds: [],
      caption: 'spoiler',
      chapterId: null,
      requiresEvidenceIds: [],
      revealsHiddenCause: true,
      hiddenCauseId: 'hidden-cause-compromised-credentials',
    } as unknown as PresentationHintV1;

    const gated = filterSafePresentationHints(
      [
        unsafe,
        ...SILENT_RELAY_PRESENTATION_HINTS.filter((h) => h.id === 'hint_evidence_workstation'),
      ],
      early,
      warnings,
    );
    expect(gated).toHaveLength(0);
    expect(warnings.some((w) => w.includes('Blocked') || w.includes('Deferred'))).toBe(true);

    const late = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 180 });
    const lateWarnings: string[] = [];
    const lateGated = filterSafePresentationHints(
      SILENT_RELAY_PRESENTATION_HINTS.filter((h) => h.id === 'hint_evidence_workstation'),
      late,
      lateWarnings,
    );
    expect(lateGated).toHaveLength(1);
  });
});

/** Phase 28 cinematic incident replay contracts. */

import { z } from 'zod';

import { incidentIdSchema, runIdSchema, sequenceSchema, simTimestampSchema } from './primitives';
import {
  CAMERA_DIRECTIVE_SCHEMA_VERSION,
  CINEMATIC_BEAT_SCHEMA_VERSION,
  CINEMATIC_CHAPTER_SCHEMA_VERSION,
  CINEMATIC_PLAN_SCHEMA_VERSION,
  CINEMATIC_PLAYBACK_STATE_SCHEMA_VERSION,
  CINEMATIC_PROVENANCE_SCHEMA_VERSION,
  PRESENTATION_HINT_SCHEMA_VERSION,
} from './versioning';

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .refine((v) => v === expected);

export const cinematicErrorCodeSchema = z.enum([
  'CINEMATIC_VALIDATION_FAILED',
  'CINEMATIC_INCOMPATIBLE',
  'CINEMATIC_MISSING_REFERENCE',
  'CINEMATIC_HINT_BLOCKED',
  'CINEMATIC_REPLAY_UNAVAILABLE',
]);

export const cinematicBeatKindSchema = z.enum([
  'establishing',
  'incident_origin',
  'evidence_focus',
  'path_trace',
  'agent_investigation',
  'risk_change',
  'proposal_focus',
  'approval_moment',
  'consequence_reveal',
  'report_focus',
  'overview',
]);

export const cameraDirectiveKindSchema = z.enum([
  'establishing',
  'entity_focus',
  'path_trace',
  'agent_focus',
  'approval',
  'consequence',
  'overview',
]);

export const cinematicProvenanceSourceSchema = z.enum([
  'replay_state',
  'presentation_hint',
  'default_planner',
]);

export const presentationHintKindSchema = z.enum(['emphasis', 'chapter_anchor', 'caption']);

export const cinematicSessionModeSchema = z.enum(['normal', 'cinematic']);

export const cinematicDirectorStatusSchema = z.enum(['idle', 'playing', 'paused', 'free_camera']);

export const cinematicPlaybackSpeedSchema = z.enum(['0.5x', '1x', '2x', '4x']);

export const cameraBookmarkWireSchema = z
  .object({
    position: z
      .object({
        x: z.number(),
        y: z.number(),
        z: z.number(),
      })
      .strict(),
    target: z
      .object({
        x: z.number(),
        y: z.number(),
        z: z.number(),
      })
      .strict(),
    fov: z.number().positive(),
  })
  .strict();

export const cinematicProvenanceSchema = z
  .object({
    schemaVersion: schemaVersionCheck(CINEMATIC_PROVENANCE_SCHEMA_VERSION),
    runId: runIdSchema,
    sequence: sequenceSchema,
    simTime: simTimestampSchema.nullable().optional(),
    entityIds: z.array(z.string().min(1).max(128)).default([]),
    incidentId: incidentIdSchema.nullable().optional(),
    source: cinematicProvenanceSourceSchema,
    stateDigest: z.string().min(1).max(128).nullable().optional(),
  })
  .strict();

export const cameraDirectiveSchema = z
  .object({
    schemaVersion: schemaVersionCheck(CAMERA_DIRECTIVE_SCHEMA_VERSION),
    id: z.string().min(1).max(128),
    kind: cameraDirectiveKindSchema,
    focusEntityIds: z.array(z.string().min(1).max(128)).default([]),
    pathEntityIds: z.array(z.string().min(1).max(128)).default([]),
    bookmark: cameraBookmarkWireSchema.nullable().optional(),
    transitionMs: z.number().int().min(0).max(30_000).default(800),
    reducedMotionJump: z.boolean().default(true),
  })
  .strict();

export const cinematicBeatSchema = z
  .object({
    schemaVersion: schemaVersionCheck(CINEMATIC_BEAT_SCHEMA_VERSION),
    id: z.string().min(1).max(128),
    chapterId: z.string().min(1).max(128),
    kind: cinematicBeatKindSchema,
    sequence: sequenceSchema,
    simTime: simTimestampSchema.nullable().optional(),
    caption: z.string().min(1).max(512),
    entityIds: z.array(z.string().min(1).max(128)).default([]),
    pathEntityIds: z.array(z.string().min(1).max(128)).default([]),
    cameraDirectiveId: z.string().min(1).max(128),
    provenance: cinematicProvenanceSchema,
    priority: z.number().int().min(0).max(1000).default(100),
    tieBreaker: z.number().int().min(0).max(1_000_000).default(0),
  })
  .strict();

export const cinematicChapterSchema = z
  .object({
    schemaVersion: schemaVersionCheck(CINEMATIC_CHAPTER_SCHEMA_VERSION),
    id: z.string().min(1).max(128),
    title: z.string().min(1).max(256),
    summary: z.string().min(1).max(512),
    fromSequence: sequenceSchema,
    toSequence: sequenceSchema,
    beatIds: z.array(z.string().min(1).max(128)).default([]),
    order: z.number().int().min(0).max(1000),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.toSequence < value.fromSequence) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'toSequence must be >= fromSequence',
      });
    }
  });

export const presentationHintSchema = z
  .object({
    schemaVersion: schemaVersionCheck(PRESENTATION_HINT_SCHEMA_VERSION),
    id: z.string().min(1).max(128),
    scenarioId: z.string().min(1).max(128),
    kind: presentationHintKindSchema,
    sequence: sequenceSchema,
    entityIds: z.array(z.string().min(1).max(128)).default([]),
    caption: z.string().max(512).nullable().optional(),
    chapterId: z.string().min(1).max(128).nullable().optional(),
    requiresEvidenceIds: z.array(z.string().min(1).max(128)).default([]),
    revealsHiddenCause: z.boolean().default(false),
    hiddenCauseId: z.string().min(1).max(128).nullable().optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.revealsHiddenCause) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Presentation hints must not reveal hidden causes',
      });
    }
    if (value.hiddenCauseId != null) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'hiddenCauseId is forbidden on safe presentation hints',
      });
    }
  });

export const cinematicPlaybackStateSchema = z
  .object({
    schemaVersion: schemaVersionCheck(CINEMATIC_PLAYBACK_STATE_SCHEMA_VERSION),
    runId: runIdSchema,
    mode: cinematicSessionModeSchema,
    status: cinematicDirectorStatusSchema,
    chapterIndex: z.number().int().min(0),
    beatIndex: z.number().int().min(0),
    speed: cinematicPlaybackSpeedSchema,
    reducedMotion: z.boolean().default(false),
    captionsEnabled: z.boolean().default(true),
    activeBeatId: z.string().min(1).max(128).nullable().optional(),
    activeChapterId: z.string().min(1).max(128).nullable().optional(),
  })
  .strict();

export const cinematicPlanSchema = z
  .object({
    schemaVersion: schemaVersionCheck(CINEMATIC_PLAN_SCHEMA_VERSION),
    runId: runIdSchema,
    chapters: z.array(cinematicChapterSchema).min(1),
    beats: z.array(cinematicBeatSchema).min(1),
    cameraDirectives: z.array(cameraDirectiveSchema).min(1),
    warnings: z.array(z.string().max(512)).default([]),
  })
  .strict();

export type CinematicErrorCode = z.infer<typeof cinematicErrorCodeSchema>;
export type CinematicBeatKind = z.infer<typeof cinematicBeatKindSchema>;
export type CameraDirectiveKind = z.infer<typeof cameraDirectiveKindSchema>;
export type CinematicProvenanceSource = z.infer<typeof cinematicProvenanceSourceSchema>;
export type PresentationHintKind = z.infer<typeof presentationHintKindSchema>;
export type CinematicSessionMode = z.infer<typeof cinematicSessionModeSchema>;
export type CinematicDirectorStatus = z.infer<typeof cinematicDirectorStatusSchema>;
export type CinematicPlaybackSpeed = z.infer<typeof cinematicPlaybackSpeedSchema>;
export type CameraBookmarkWire = z.infer<typeof cameraBookmarkWireSchema>;
export type CinematicProvenanceV1 = z.infer<typeof cinematicProvenanceSchema>;
export type CameraDirectiveV1 = z.infer<typeof cameraDirectiveSchema>;
export type CinematicBeatV1 = z.infer<typeof cinematicBeatSchema>;
export type CinematicChapterV1 = z.infer<typeof cinematicChapterSchema>;
export type PresentationHintV1 = z.infer<typeof presentationHintSchema>;
export type CinematicPlaybackStateV1 = z.infer<typeof cinematicPlaybackStateSchema>;
export type CinematicPlanV1 = z.infer<typeof cinematicPlanSchema>;

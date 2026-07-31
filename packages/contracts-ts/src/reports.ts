/** Phase 23 SCRIBE after-action report contracts. */

import { z } from 'zod';

import {
  agentSessionIdSchema,
  agentTaskIdSchema,
  assetIdSchema,
  eventIdSchema,
  evidenceIdSchema,
  hypothesisIdSchema,
  incidentIdSchema,
  proposalIdSchema,
  runIdSchema,
  traceIdSchema,
  utcTimestampSchema,
} from './primitives';
import {
  AFTER_ACTION_REPORT_SCHEMA_VERSION,
  AFTER_ACTION_REPORT_SOURCE_SCHEMA_VERSION,
  GROUNDING_VALIDATION_RESULT_SCHEMA_VERSION,
  REPORT_CITATION_SCHEMA_VERSION,
  REPORT_CLAIM_SCHEMA_VERSION,
  REPORT_EXPORT_ARTIFACT_SCHEMA_VERSION,
  REPORT_TIMELINE_ENTRY_SCHEMA_VERSION,
  REPORT_VERSION_SCHEMA_VERSION,
  TRIGGER_SCRIBE_REQUEST_SCHEMA_VERSION,
} from './versioning';

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .refine((v) => v === expected);

export const reportClaimCategorySchema = z.enum([
  'observed_fact',
  'persisted_event',
  'detection_score',
  'graph_risk',
  'investigation_evidence',
  'oracle_hypothesis',
  'bastion_proposal',
  'warden_policy_decision',
  'human_decision',
  'agent_inference',
  'unsupported',
  'uncertain',
]);

export const reportCitationKindSchema = z.enum([
  'event',
  'evidence',
  'hypothesis',
  'proposal',
  'policy_decision',
  'model_score',
  'agent_task',
  'agent_session',
  'alert',
  'asset',
]);

export const reportExportFormatSchema = z.enum(['markdown', 'json', 'html']);

export const reportGenerationStatusSchema = z.enum(['completed', 'grounding_fallback', 'failed']);

/**
 * How the narrative content of a report version was produced. `deterministic` reports are
 * assembled purely from persisted run state with no model in the loop and must never be
 * presented as agent-authored narrative.
 */
export const reportGenerationModeSchema = z.enum(['llm_narrative', 'deterministic']);

export const reportCitationSchema = z
  .object({
    schemaVersion: schemaVersionCheck(REPORT_CITATION_SCHEMA_VERSION),
    kind: reportCitationKindSchema,
    referenceId: z.string().min(1).max(128),
    label: z.string().min(1).max(512),
    sequence: z.number().int().min(0).nullable().optional(),
    rationale: z.string().max(2048).default(''),
  })
  .strict();

export const reportClaimSchema = z
  .object({
    schemaVersion: schemaVersionCheck(REPORT_CLAIM_SCHEMA_VERSION),
    claimId: z.string().min(1).max(64),
    category: reportClaimCategorySchema,
    text: z.string().min(1).max(4096),
    confidence: z.number().min(0).max(1).nullable().optional(),
    uncertainty: z.string().max(1024).nullable().optional(),
    citations: z.array(reportCitationSchema).default([]),
    grounded: z.boolean().default(true),
    rejectionReason: z.string().max(1024).nullable().optional(),
  })
  .strict();

export const reportTimelineEntrySchema = z
  .object({
    schemaVersion: schemaVersionCheck(REPORT_TIMELINE_ENTRY_SCHEMA_VERSION),
    sequence: z.number().int().min(0),
    eventId: eventIdSchema,
    eventType: z.string().min(1).max(128),
    label: z.string().min(1).max(512),
    timestamp: utcTimestampSchema,
    status: z.string().max(64).default('normal'),
    relatedEvidenceIds: z.array(evidenceIdSchema).default([]),
    relatedHypothesisIds: z.array(hypothesisIdSchema).default([]),
  })
  .strict();

export const afterActionReportSourceSchema = z
  .object({
    schemaVersion: schemaVersionCheck(AFTER_ACTION_REPORT_SOURCE_SCHEMA_VERSION),
    runId: runIdSchema,
    incidentId: incidentIdSchema,
    sourceSequenceFrom: z.number().int().min(0),
    sourceSequenceTo: z.number().int().min(0),
    eventIds: z.array(eventIdSchema).default([]),
    evidenceIds: z.array(evidenceIdSchema).default([]),
    hypothesisIds: z.array(hypothesisIdSchema).default([]),
    proposalIds: z.array(proposalIdSchema).default([]),
    policyDecisionIds: z.array(z.string()).default([]),
    affectedAssetIds: z.array(assetIdSchema).default([]),
    alertIds: z.array(z.string()).default([]),
    agentSessionIds: z.array(agentSessionIdSchema).default([]),
    timeline: z.array(reportTimelineEntrySchema).default([]),
    investigationSummary: z.record(z.unknown()).default({}),
  })
  .strict();

export const afterActionReportSchema = z
  .object({
    schemaVersion: schemaVersionCheck(AFTER_ACTION_REPORT_SCHEMA_VERSION),
    id: z.string().min(1).max(64),
    runId: runIdSchema,
    incidentId: incidentIdSchema,
    versionNumber: z.number().int().min(1),
    title: z.string().min(1).max(256),
    executiveSummary: z.string().min(1).max(8192),
    chronologySummary: z.string().min(1).max(8192),
    claims: z.array(reportClaimSchema).default([]),
    timeline: z.array(reportTimelineEntrySchema).default([]),
    lessons: z.array(z.string()).default([]),
    contradictions: z.array(z.string()).default([]),
    uncertainties: z.array(z.string()).default([]),
    source: afterActionReportSourceSchema,
    groundingFallback: z.boolean().default(false),
    generationMode: reportGenerationModeSchema.default('deterministic'),
    narrativeProviderId: z.string().max(64).nullable().optional(),
    narrativePromptVersion: z.string().max(64).nullable().optional(),
    sessionId: agentSessionIdSchema.nullable().optional(),
    taskId: agentTaskIdSchema.nullable().optional(),
    checksum: z.string().min(64).max(64),
    createdAt: utcTimestampSchema,
  })
  .strict();

export const reportVersionSchema = z
  .object({
    schemaVersion: schemaVersionCheck(REPORT_VERSION_SCHEMA_VERSION),
    id: z.string().min(1).max(64),
    runId: runIdSchema,
    incidentId: incidentIdSchema,
    versionNumber: z.number().int().min(1),
    reportId: z.string().min(1).max(64),
    status: reportGenerationStatusSchema,
    sourceSequenceFrom: z.number().int().min(0),
    sourceSequenceTo: z.number().int().min(0),
    providerId: z.string().max(64).nullable().optional(),
    promptVersion: z.string().max(64).nullable().optional(),
    sessionId: agentSessionIdSchema.nullable().optional(),
    taskId: agentTaskIdSchema.nullable().optional(),
    checksum: z.string().min(64).max(64),
    groundingFallback: z.boolean().default(false),
    generationMode: reportGenerationModeSchema.default('deterministic'),
    createdAt: utcTimestampSchema,
  })
  .strict();

export const reportExportArtifactSchema = z
  .object({
    schemaVersion: schemaVersionCheck(REPORT_EXPORT_ARTIFACT_SCHEMA_VERSION),
    id: z.string().min(1).max(64),
    reportVersionId: z.string().min(1).max(64),
    runId: runIdSchema,
    format: reportExportFormatSchema,
    objectKey: z.string().min(1).max(512),
    checksum: z.string().min(64).max(64),
    contentType: z.string().min(1).max(128),
    sizeBytes: z.number().int().min(0),
    workspaceVersion: z.string().min(1).max(32),
    reportSchemaVersion: z.number().int().min(1),
    createdAt: utcTimestampSchema,
  })
  .strict();

export const groundingValidationResultSchema = z
  .object({
    schemaVersion: schemaVersionCheck(GROUNDING_VALIDATION_RESULT_SCHEMA_VERSION),
    claimId: z.string().min(1).max(64),
    valid: z.boolean(),
    citationResults: z.array(z.record(z.unknown())).default([]),
    rejectionReason: z.string().max(1024).nullable().optional(),
    downgradedCategory: reportClaimCategorySchema.nullable().optional(),
  })
  .strict();

export const triggerScribeRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(TRIGGER_SCRIBE_REQUEST_SCHEMA_VERSION),
    runId: runIdSchema,
    incidentId: incidentIdSchema.nullable().optional(),
    traceId: traceIdSchema,
    providerId: z.string().default('mock'),
    idempotencyKey: z.string().min(1).max(256),
    regenerate: z.boolean().default(false),
  })
  .strict();

export type ReportClaimCategoryV1 = z.infer<typeof reportClaimCategorySchema>;
export type ReportCitationKindV1 = z.infer<typeof reportCitationKindSchema>;
export type ReportExportFormatV1 = z.infer<typeof reportExportFormatSchema>;
export type ReportGenerationStatusV1 = z.infer<typeof reportGenerationStatusSchema>;
export type ReportGenerationModeV1 = z.infer<typeof reportGenerationModeSchema>;
export type ReportCitationV1 = z.infer<typeof reportCitationSchema>;
export type ReportClaimV1 = z.infer<typeof reportClaimSchema>;
export type ReportTimelineEntryV1 = z.infer<typeof reportTimelineEntrySchema>;
export type AfterActionReportSourceV1 = z.infer<typeof afterActionReportSourceSchema>;
export type AfterActionReportV1 = z.infer<typeof afterActionReportSchema>;
export type ReportVersionV1 = z.infer<typeof reportVersionSchema>;
export type ReportExportArtifactV1 = z.infer<typeof reportExportArtifactSchema>;
export type GroundingValidationResultV1 = z.infer<typeof groundingValidationResultSchema>;
export type TriggerScribeRequestV1 = z.infer<typeof triggerScribeRequestSchema>;

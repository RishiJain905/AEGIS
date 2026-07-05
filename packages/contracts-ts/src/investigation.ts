import { z } from 'zod';

import {
  agentSessionIdSchema,
  agentTaskIdSchema,
  alertIdSchema,
  assetIdSchema,
  evidenceIdSchema,
  incidentIdSchema,
  runIdSchema,
  traceIdSchema,
  utcTimestampSchema,
} from './primitives';
import {
  AGENT_GRAPH_OVERLAY_SCHEMA_VERSION,
  CANDIDATE_AFFECTED_ASSET_SCHEMA_VERSION,
  EVIDENCE_ATTACHMENT_SCHEMA_VERSION,
  INVESTIGATION_DETAIL_SCHEMA_VERSION,
  INVESTIGATION_NOTE_SCHEMA_VERSION,
  TRACE_INVESTIGATION_PLAN_SCHEMA_VERSION,
  WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION,
} from './versioning';

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .refine((v) => v === expected);

export const TriageEscalationLevel = {
  MONITOR: 'monitor',
  INVESTIGATE: 'investigate',
  URGENT: 'urgent',
} as const;

export const EvidenceSourceType = {
  EVENT: 'event',
  ALERT: 'alert',
  ASSET: 'asset',
  RISK_PATH: 'risk_path',
  EXISTING_EVIDENCE: 'existing_evidence',
} as const;

export const alertCorrelationDecisionSchema = z.object({
  alertIds: z.array(alertIdSchema),
  decision: z.string().min(1).max(32),
  rationale: z.string().min(1).max(2048),
  factors: z.array(z.string()).default([]),
});

export const watchtowerTriageResultSchema = z.object({
  schemaVersion: schemaVersionCheck(WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION),
  id: z.string().min(1).max(64),
  incidentId: incidentIdSchema,
  runId: runIdSchema,
  sessionId: agentSessionIdSchema,
  taskId: agentTaskIdSchema,
  alertSummaries: z.array(z.record(z.unknown())).default([]),
  groupedAlertIds: z.array(alertIdSchema).default([]),
  separatedAlertIds: z.array(alertIdSchema).default([]),
  correlationDecisions: z.array(alertCorrelationDecisionSchema).default([]),
  escalation: z.enum([
    TriageEscalationLevel.MONITOR,
    TriageEscalationLevel.INVESTIGATE,
    TriageEscalationLevel.URGENT,
  ]),
  escalationRationale: z.string().min(1).max(2048),
  confidence: z.number().min(0).max(1),
  evidenceIds: z.array(evidenceIdSchema).default([]),
  idempotencyKey: z.string().min(1).max(256),
  createdAt: utcTimestampSchema,
});

export const traceSearchStepSchema = z.object({
  toolName: z.string().min(1).max(128),
  arguments: z.record(z.unknown()).default({}),
  purpose: z.string().min(1).max(512),
});

export const traceInvestigationPlanSchema = z.object({
  schemaVersion: schemaVersionCheck(TRACE_INVESTIGATION_PLAN_SCHEMA_VERSION),
  id: z.string().min(1).max(64),
  incidentId: incidentIdSchema,
  runId: runIdSchema,
  sessionId: agentSessionIdSchema,
  taskId: agentTaskIdSchema,
  seedAssetIds: z.array(assetIdSchema).default([]),
  timeWindowStartSequence: z.number().int().min(0).nullable().optional(),
  timeWindowEndSequence: z.number().int().min(0).nullable().optional(),
  maxHops: z.number().int().min(1).max(8),
  maxToolCalls: z.number().int().min(1).max(50),
  maxTokens: z.number().int().min(1).max(100_000),
  searchSteps: z.array(traceSearchStepSchema).default([]),
  rationale: z.string().min(1).max(2048),
  createdAt: utcTimestampSchema,
});

export const evidenceProvenanceSchema = z.object({
  sourceType: z.enum([
    EvidenceSourceType.EVENT,
    EvidenceSourceType.ALERT,
    EvidenceSourceType.ASSET,
    EvidenceSourceType.RISK_PATH,
    EvidenceSourceType.EXISTING_EVIDENCE,
  ]),
  sourceId: z.string().min(1).max(128),
  summary: z.string().min(1).max(2048),
  collectedByTool: z.string().max(128).nullable().optional(),
  collectedAtSequence: z.number().int().min(0).nullable().optional(),
});

export const evidenceAttachmentSchema = z.object({
  schemaVersion: schemaVersionCheck(EVIDENCE_ATTACHMENT_SCHEMA_VERSION),
  id: z.string().min(1).max(64),
  incidentId: incidentIdSchema,
  sessionId: agentSessionIdSchema,
  taskId: agentTaskIdSchema,
  provenance: evidenceProvenanceSchema,
  evidenceId: evidenceIdSchema.nullable().optional(),
  assetId: assetIdSchema.nullable().optional(),
  isContradiction: z.boolean().default(false),
  confidence: z.number().min(0).max(1),
  rationale: z.string().min(1).max(2048),
  createdAt: utcTimestampSchema,
});

export const candidateAffectedAssetSchema = z.object({
  schemaVersion: schemaVersionCheck(CANDIDATE_AFFECTED_ASSET_SCHEMA_VERSION),
  id: z.string().min(1).max(64),
  incidentId: incidentIdSchema,
  assetId: assetIdSchema,
  confidence: z.number().min(0).max(1),
  evidenceIds: z.array(evidenceIdSchema).default([]),
  rationale: z.string().min(1).max(2048),
  createdAt: utcTimestampSchema,
});

export const investigationNoteSchema = z.object({
  schemaVersion: schemaVersionCheck(INVESTIGATION_NOTE_SCHEMA_VERSION),
  id: z.string().min(1).max(64),
  incidentId: incidentIdSchema,
  sessionId: agentSessionIdSchema,
  taskId: agentTaskIdSchema,
  note: z.string().min(1).max(4096),
  evidenceIds: z.array(evidenceIdSchema).min(1),
  createdAt: utcTimestampSchema,
});

export const graphOverlayHighlightSchema = z.object({
  entityId: z.string().min(1).max(128),
  entityType: z.string().min(1).max(32),
  highlightKind: z.string().min(1).max(32),
  label: z.string().max(256).default(''),
});

export const agentGraphOverlaySchema = z.object({
  schemaVersion: schemaVersionCheck(AGENT_GRAPH_OVERLAY_SCHEMA_VERSION),
  id: z.string().min(1).max(64),
  incidentId: incidentIdSchema,
  runId: runIdSchema,
  sessionId: agentSessionIdSchema,
  taskId: agentTaskIdSchema,
  highlights: z.array(graphOverlayHighlightSchema).default([]),
  edgeHighlights: z.array(graphOverlayHighlightSchema).default([]),
  rationale: z.string().min(1).max(2048),
  createdAt: utcTimestampSchema,
});

export const investigationDetailSchema = z.object({
  schemaVersion: schemaVersionCheck(INVESTIGATION_DETAIL_SCHEMA_VERSION),
  incidentId: incidentIdSchema,
  runId: runIdSchema,
  triageResults: z.array(watchtowerTriageResultSchema).default([]),
  plans: z.array(traceInvestigationPlanSchema).default([]),
  evidenceAttachments: z.array(evidenceAttachmentSchema).default([]),
  notes: z.array(investigationNoteSchema).default([]),
  candidateAssets: z.array(candidateAffectedAssetSchema).default([]),
  overlays: z.array(agentGraphOverlaySchema).default([]),
});

export const triggerWatchtowerRequestSchema = z.object({
  schemaVersion: z.literal(1),
  runId: runIdSchema,
  alertIds: z.array(alertIdSchema).default([]),
  traceId: traceIdSchema,
  providerId: z.string().default('mock'),
  idempotencyKey: z.string().min(1).max(256),
});

export type WatchtowerTriageResultV1 = z.infer<typeof watchtowerTriageResultSchema>;
export type TraceInvestigationPlanV1 = z.infer<typeof traceInvestigationPlanSchema>;
export type EvidenceAttachmentV1 = z.infer<typeof evidenceAttachmentSchema>;
export type CandidateAffectedAssetV1 = z.infer<typeof candidateAffectedAssetSchema>;
export type InvestigationNoteV1 = z.infer<typeof investigationNoteSchema>;
export type AgentGraphOverlayV1 = z.infer<typeof agentGraphOverlaySchema>;
export type InvestigationDetailV1 = z.infer<typeof investigationDetailSchema>;

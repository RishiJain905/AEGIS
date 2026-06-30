import { z } from 'zod';

import {
  actionIdSchema,
  agentSessionIdSchema,
  alertIdSchema,
  approvalIdSchema,
  assetIdSchema,
  authoredIdSchema,
  eventIdSchema,
  evidenceIdSchema,
  hypothesisIdSchema,
  incidentIdSchema,
  modelIdSchema,
  proposalIdSchema,
  revisionSchema,
  runIdSchema,
  scenarioIdSchema,
  simTimestampSchema,
  traceIdSchema,
  utcTimestampSchema,
} from './primitives';
import {
  ACTION_PROPOSAL_SCHEMA_VERSION,
  AGENT_SESSION_SCHEMA_VERSION,
  ALERT_SCHEMA_VERSION,
  APPROVAL_SCHEMA_VERSION,
  EVIDENCE_SCHEMA_VERSION,
  EXECUTED_ACTION_SCHEMA_VERSION,
  HYPOTHESIS_SCHEMA_VERSION,
  INCIDENT_SCHEMA_VERSION,
  MODEL_MANIFEST_SCHEMA_VERSION,
  MODEL_SCORE_SCHEMA_VERSION,
  RUN_SCHEMA_VERSION,
  SCENARIO_SCHEMA_VERSION,
  SCENARIO_VERSION_SCHEMA_VERSION,
} from './versioning';

export const IncidentState = {
  OPEN: 'open',
  TRIAGED: 'triaged',
  INVESTIGATING: 'investigating',
  CONTAINMENT_PROPOSED: 'containment_proposed',
  APPROVAL_PENDING: 'approval_pending',
  CONTAINING: 'containing',
  MONITORING: 'monitoring',
  RESOLVED: 'resolved',
  CLOSED: 'closed',
} as const;

export const AgentSessionState = {
  QUEUED: 'queued',
  GATHERING: 'gathering',
  HYPOTHESIZING: 'hypothesizing',
  VERIFYING: 'verifying',
  PROPOSING: 'proposing',
  APPROVAL_PENDING: 'approval_pending',
  EXECUTING: 'executing',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const;

export const AgentRole = {
  WATCHTOWER: 'WATCHTOWER',
  TRACE: 'TRACE',
  ORACLE: 'ORACLE',
  BASTION: 'BASTION',
  WARDEN: 'WARDEN',
  SCRIBE: 'SCRIBE',
} as const;

export const ActionClass = {
  READ_ONLY: 'class_0',
  LOW_IMPACT: 'class_1',
  OPERATIONAL: 'class_2',
  CRITICAL: 'class_3',
} as const;

export const ProposalStatus = {
  PENDING: 'pending',
  APPROVED: 'approved',
  REJECTED: 'rejected',
  EXECUTED: 'executed',
  CANCELLED: 'cancelled',
} as const;

export const ApprovalDecision = {
  APPROVED: 'approved',
  REJECTED: 'rejected',
} as const;

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .superRefine((value, ctx) => {
      if (value !== expected) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `Unsupported schema version: ${String(value)}`,
        });
      }
    });

export const scenarioSchema = z
  .object({
    schemaVersion: schemaVersionCheck(SCENARIO_SCHEMA_VERSION),
    id: scenarioIdSchema,
    name: z.string().min(1),
    description: z.string().default(''),
    createdAt: utcTimestampSchema,
  })
  .strict();

export const scenarioVersionSchema = z
  .object({
    schemaVersion: schemaVersionCheck(SCENARIO_VERSION_SCHEMA_VERSION),
    id: authoredIdSchema,
    scenarioId: scenarioIdSchema,
    version: z.string().min(1),
    requiredPlatformVersion: z.string().min(1),
    publishedAt: utcTimestampSchema,
  })
  .strict();

export const runSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RUN_SCHEMA_VERSION),
    id: runIdSchema,
    scenarioVersionId: authoredIdSchema,
    seed: z.number().int(),
    status: z.string().min(1),
    startedAt: utcTimestampSchema,
    simTime: simTimestampSchema,
    revision: revisionSchema,
  })
  .strict();

export const alertSchema = z
  .object({
    schemaVersion: schemaVersionCheck(ALERT_SCHEMA_VERSION),
    id: alertIdSchema,
    runId: runIdSchema,
    title: z.string().min(1),
    severity: z.string().min(1),
    sourceEventId: eventIdSchema,
    assetId: assetIdSchema,
    createdAt: utcTimestampSchema,
  })
  .strict();

export const incidentSchema = z
  .object({
    schemaVersion: schemaVersionCheck(INCIDENT_SCHEMA_VERSION),
    id: incidentIdSchema,
    runId: runIdSchema,
    title: z.string().min(1),
    state: z.enum([
      'open',
      'triaged',
      'investigating',
      'containment_proposed',
      'approval_pending',
      'containing',
      'monitoring',
      'resolved',
      'closed',
    ]),
    alertIds: z.array(alertIdSchema),
    createdAt: utcTimestampSchema,
    updatedAt: utcTimestampSchema,
    revision: revisionSchema,
  })
  .strict();

export const evidenceSchema = z
  .object({
    schemaVersion: schemaVersionCheck(EVIDENCE_SCHEMA_VERSION),
    id: evidenceIdSchema,
    runId: runIdSchema,
    sourceEventId: eventIdSchema,
    summary: z.string().min(1),
    assetId: assetIdSchema.optional(),
    createdAt: utcTimestampSchema,
  })
  .strict();

export const hypothesisSchema = z
  .object({
    schemaVersion: schemaVersionCheck(HYPOTHESIS_SCHEMA_VERSION),
    id: hypothesisIdSchema,
    incidentId: incidentIdSchema,
    statement: z.string().min(1),
    confidence: z.number().min(0).max(1),
    evidenceIds: z.array(evidenceIdSchema),
    createdAt: utcTimestampSchema,
  })
  .strict();

export const agentSessionSchema = z
  .object({
    schemaVersion: schemaVersionCheck(AGENT_SESSION_SCHEMA_VERSION),
    id: agentSessionIdSchema,
    incidentId: incidentIdSchema,
    role: z.enum(['WATCHTOWER', 'TRACE', 'ORACLE', 'BASTION', 'WARDEN', 'SCRIBE']),
    state: z.enum([
      'queued',
      'gathering',
      'hypothesizing',
      'verifying',
      'proposing',
      'approval_pending',
      'executing',
      'completed',
      'failed',
      'cancelled',
    ]),
    traceId: traceIdSchema,
    createdAt: utcTimestampSchema,
    updatedAt: utcTimestampSchema,
  })
  .strict();

export const actionProposalSchema = z
  .object({
    schemaVersion: schemaVersionCheck(ACTION_PROPOSAL_SCHEMA_VERSION),
    id: proposalIdSchema,
    incidentId: incidentIdSchema,
    agentSessionId: agentSessionIdSchema,
    actionClass: z.enum(['class_0', 'class_1', 'class_2', 'class_3']),
    targetAssetId: assetIdSchema,
    command: z.string().min(1),
    status: z.enum(['pending', 'approved', 'rejected', 'executed', 'cancelled']),
    rationale: z.string().default(''),
    revision: revisionSchema,
    createdAt: utcTimestampSchema,
  })
  .strict();

export const approvalSchema = z
  .object({
    schemaVersion: schemaVersionCheck(APPROVAL_SCHEMA_VERSION),
    id: approvalIdSchema,
    proposalId: proposalIdSchema,
    decision: z.enum(['approved', 'rejected']),
    approverId: z.string().min(1),
    proposalRevision: revisionSchema,
    decidedAt: utcTimestampSchema,
  })
  .strict();

export const executedActionSchema = z
  .object({
    schemaVersion: schemaVersionCheck(EXECUTED_ACTION_SCHEMA_VERSION),
    id: actionIdSchema,
    proposalId: proposalIdSchema,
    runId: runIdSchema,
    resultEventId: eventIdSchema,
    idempotencyKey: z.string().min(1),
    executedAt: utcTimestampSchema,
  })
  .strict();

export const modelManifestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(MODEL_MANIFEST_SCHEMA_VERSION),
    id: modelIdSchema,
    semanticVersion: z.string().min(1),
    algorithm: z.string().min(1),
    featureSchemaVersion: z.number().int().min(1),
    artifactChecksum: z.string().min(1),
    artifactObjectKey: z.string().min(1),
    evaluationMetrics: z.record(z.unknown()).default({}),
    knownLimitations: z.array(z.string()).default([]),
    createdAt: utcTimestampSchema,
  })
  .strict();

export const modelScoreSchema = z
  .object({
    schemaVersion: schemaVersionCheck(MODEL_SCORE_SCHEMA_VERSION),
    modelVersionId: modelIdSchema,
    entityId: assetIdSchema,
    score: z.number().min(0).max(1),
    riskBand: z.string().min(1),
    featureSchemaVersion: z.number().int().min(1),
    explanation: z.record(z.unknown()).default({}),
    scoredAt: utcTimestampSchema,
    sourceEventId: eventIdSchema.optional(),
  })
  .strict();

export type ScenarioV1 = z.infer<typeof scenarioSchema>;
export type ScenarioVersionV1 = z.infer<typeof scenarioVersionSchema>;
export type RunV1 = z.infer<typeof runSchema>;
export type AlertV1 = z.infer<typeof alertSchema>;
export type IncidentV1 = z.infer<typeof incidentSchema>;
export type EvidenceV1 = z.infer<typeof evidenceSchema>;
export type HypothesisV1 = z.infer<typeof hypothesisSchema>;
export type AgentSessionV1 = z.infer<typeof agentSessionSchema>;
export type ActionProposalV1 = z.infer<typeof actionProposalSchema>;
export type ApprovalV1 = z.infer<typeof approvalSchema>;
export type ExecutedActionV1 = z.infer<typeof executedActionSchema>;
export type ModelManifestV1 = z.infer<typeof modelManifestSchema>;
export type ModelScoreV1 = z.infer<typeof modelScoreSchema>;

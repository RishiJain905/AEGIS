import { z } from 'zod';

import {
  agentSessionIdSchema,
  agentTaskIdSchema,
  evidenceIdSchema,
  hypothesisIdSchema,
  incidentIdSchema,
  runIdSchema,
  traceIdSchema,
  utcTimestampSchema,
} from './primitives';
import {
  CONFIDENCE_ASSESSMENT_SCHEMA_VERSION,
  CONTRADICTION_LINK_SCHEMA_VERSION,
  HYPOTHESIS_CLAIM_SCHEMA_VERSION,
  HYPOTHESIS_COMPARISON_SCHEMA_VERSION,
  HYPOTHESIS_REVISION_SCHEMA_VERSION,
  TRIGGER_ORACLE_REQUEST_SCHEMA_VERSION,
  VERIFICATION_REQUEST_SCHEMA_VERSION,
} from './versioning';

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .refine((v) => v === expected);

export const HypothesisFamilyV1 = {
  LATERAL_MOVEMENT: 'lateral_movement',
  CREDENTIAL_ABUSE: 'credential_abuse',
  BENIGN_ANOMALY: 'benign_anomaly',
  SUPPLY_CHAIN: 'supply_chain',
  INSIDER_THREAT: 'insider_threat',
  DATA_EXFILTRATION: 'data_exfiltration',
} as const;

export const ClaimKindV1 = {
  OBSERVED_FACT: 'observed_fact',
  MODEL_SCORE: 'model_score',
  GRAPH_RISK: 'graph_risk',
  AGENT_INFERENCE: 'agent_inference',
  UNSUPPORTED_CLAIM: 'unsupported_claim',
} as const;

export const HypothesisStatusV1 = {
  ACTIVE: 'active',
  SUPERSEDED: 'superseded',
  RETIRED: 'retired',
} as const;

export const hypothesisClaimSchema = z.object({
  schemaVersion: schemaVersionCheck(HYPOTHESIS_CLAIM_SCHEMA_VERSION),
  kind: z.enum([
    ClaimKindV1.OBSERVED_FACT,
    ClaimKindV1.MODEL_SCORE,
    ClaimKindV1.GRAPH_RISK,
    ClaimKindV1.AGENT_INFERENCE,
    ClaimKindV1.UNSUPPORTED_CLAIM,
  ]),
  text: z.string().min(1).max(2048),
  evidenceIds: z.array(evidenceIdSchema).default([]),
  attachmentIds: z.array(z.string()).default([]),
  isAssumption: z.boolean().default(false),
});

export const confidenceAssessmentSchema = z.object({
  schemaVersion: schemaVersionCheck(CONFIDENCE_ASSESSMENT_SCHEMA_VERSION),
  point: z.number().min(0).max(1),
  min: z.number().min(0).max(1),
  max: z.number().min(0).max(1),
  coverage: z.number().min(0).max(1),
  contradictionPenalty: z.number().min(0).max(1),
  explanation: z.string().min(1).max(2048),
});

export const contradictionLinkSchema = z.object({
  schemaVersion: schemaVersionCheck(CONTRADICTION_LINK_SCHEMA_VERSION),
  supportingEvidenceIds: z.array(evidenceIdSchema).default([]),
  contradictingEvidenceIds: z.array(evidenceIdSchema).default([]),
  supportingAttachmentIds: z.array(z.string()).default([]),
  contradictingAttachmentIds: z.array(z.string()).default([]),
  rationale: z.string().min(1).max(2048),
});

export const hypothesisRevisionSchema = z.object({
  schemaVersion: schemaVersionCheck(HYPOTHESIS_REVISION_SCHEMA_VERSION),
  id: z.string().min(1).max(64),
  hypothesisId: hypothesisIdSchema,
  incidentId: incidentIdSchema,
  sessionId: agentSessionIdSchema,
  taskId: agentTaskIdSchema,
  revisionNumber: z.number().int().min(1),
  claim: z.string().min(1).max(4096),
  family: z.enum([
    HypothesisFamilyV1.LATERAL_MOVEMENT,
    HypothesisFamilyV1.CREDENTIAL_ABUSE,
    HypothesisFamilyV1.BENIGN_ANOMALY,
    HypothesisFamilyV1.SUPPLY_CHAIN,
    HypothesisFamilyV1.INSIDER_THREAT,
    HypothesisFamilyV1.DATA_EXFILTRATION,
  ]),
  confidence: confidenceAssessmentSchema,
  claims: z.array(hypothesisClaimSchema).default([]),
  assumptions: z.array(z.string()).default([]),
  supportingEvidenceIds: z.array(evidenceIdSchema).default([]),
  contradictingEvidenceIds: z.array(evidenceIdSchema).default([]),
  unknowns: z.array(z.string()).default([]),
  predictions: z.array(z.string()).default([]),
  contradictionLinks: z.array(contradictionLinkSchema).default([]),
  status: z
    .enum([HypothesisStatusV1.ACTIVE, HypothesisStatusV1.SUPERSEDED, HypothesisStatusV1.RETIRED])
    .default(HypothesisStatusV1.ACTIVE),
  rationale: z.string().min(1).max(2048),
  createdAt: utcTimestampSchema,
});

export const hypothesisComparisonEntrySchema = z.object({
  hypothesisId: hypothesisIdSchema,
  revisionId: z.string().min(1).max(64),
  sharedEvidenceIds: z.array(evidenceIdSchema).default([]),
  uniqueEvidenceIds: z.array(evidenceIdSchema).default([]),
  contradictingEvidenceIds: z.array(evidenceIdSchema).default([]),
  confidencePoint: z.number().min(0).max(1),
});

export const hypothesisComparisonSchema = z.object({
  schemaVersion: schemaVersionCheck(HYPOTHESIS_COMPARISON_SCHEMA_VERSION),
  id: z.string().min(1).max(64),
  incidentId: incidentIdSchema,
  sessionId: agentSessionIdSchema,
  taskId: agentTaskIdSchema,
  entries: z.array(hypothesisComparisonEntrySchema).min(2),
  summary: z.string().min(1).max(4096),
  matrix: z.record(z.unknown()).default({}),
  createdAt: utcTimestampSchema,
});

export const verificationRequestSchema = z.object({
  schemaVersion: schemaVersionCheck(VERIFICATION_REQUEST_SCHEMA_VERSION),
  id: z.string().min(1).max(64),
  incidentId: incidentIdSchema,
  hypothesisId: hypothesisIdSchema,
  sessionId: agentSessionIdSchema,
  taskId: agentTaskIdSchema,
  purpose: z.string().min(1).max(2048),
  targetEvidenceIds: z.array(evidenceIdSchema).default([]),
  idempotencyKey: z.string().min(1).max(256),
  createdAt: utcTimestampSchema,
});

export const triggerOracleRequestSchema = z.object({
  schemaVersion: schemaVersionCheck(TRIGGER_ORACLE_REQUEST_SCHEMA_VERSION),
  runId: runIdSchema,
  incidentId: incidentIdSchema.nullable().optional(),
  traceId: traceIdSchema,
  providerId: z.string().default('mock'),
  idempotencyKey: z.string().min(1).max(256),
  revisionMode: z.boolean().default(false),
});

export type HypothesisClaimV1 = z.infer<typeof hypothesisClaimSchema>;
export type ConfidenceAssessmentV1 = z.infer<typeof confidenceAssessmentSchema>;
export type ContradictionLinkV1 = z.infer<typeof contradictionLinkSchema>;
export type HypothesisRevisionV1 = z.infer<typeof hypothesisRevisionSchema>;
export type HypothesisComparisonV1 = z.infer<typeof hypothesisComparisonSchema>;
export type VerificationRequestV1 = z.infer<typeof verificationRequestSchema>;
export type TriggerOracleRequestV1 = z.infer<typeof triggerOracleRequestSchema>;

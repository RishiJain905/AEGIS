/** Phase 22 BASTION/WARDEN proposal and policy contracts. */

import { z } from 'zod';

import {
  agentSessionIdSchema,
  agentTaskIdSchema,
  assetIdSchema,
  evidenceIdSchema,
  hypothesisIdSchema,
  incidentIdSchema,
  proposalIdSchema,
  runIdSchema,
  traceIdSchema,
  utcTimestampSchema,
} from './primitives';
import {
  APPROVAL_REQUIREMENT_SCHEMA_VERSION,
  POLICY_DECISION_SCHEMA_VERSION,
  POLICY_INPUT_SCHEMA_VERSION,
  PROPOSAL_REVISION_SCHEMA_VERSION,
  RESPONSE_OPTION_SCHEMA_VERSION,
  TRIGGER_BASTION_REQUEST_SCHEMA_VERSION,
  TRIGGER_WARDEN_REQUEST_SCHEMA_VERSION,
} from './versioning';

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .refine((v) => v === expected);

export const scenarioCommandTemplateSchema = z.enum([
  'observe',
  'increase_monitoring',
  'isolate',
  'revoke_credentials',
  'restrict_access',
  'restart_service',
  'rollback_deployment',
]);

export const policyOutcomeSchema = z.enum(['allow', 'block', 'approval_required']);

export const policyReasonCodeSchema = z.enum([
  'allowed_read_only',
  'allowed_low_impact',
  'approval_required_operational',
  'approval_required_critical',
  'blocked_unknown_command',
  'blocked_malformed_command',
  'blocked_scenario_restriction',
  'blocked_criticality_threshold',
  'blocked_stale_revision',
  'blocked_invalid_action_class',
  'blocked_incident_state',
]);

export const responseOptionSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RESPONSE_OPTION_SCHEMA_VERSION),
    optionId: z.string().min(1).max(64),
    scenarioCommand: scenarioCommandTemplateSchema,
    actionClass: z.enum(['class_0', 'class_1', 'class_2', 'class_3']),
    targetAssetId: assetIdSchema,
    affectedAssetIds: z.array(assetIdSchema).default([]),
    evidenceIds: z.array(evidenceIdSchema).default([]),
    hypothesisIds: z.array(hypothesisIdSchema).default([]),
    expectedBenefit: z.string().min(1).max(2048),
    operationalCost: z.string().min(1).max(2048),
    reversibility: z.string().min(1).max(1024),
    prerequisites: z.array(z.string()).default([]),
    monitoringPlan: z.string().min(1).max(2048),
    expectedConsequences: z.string().min(1).max(2048),
    confidence: z.number().min(0).max(1),
    uncertainty: z.string().min(1).max(1024),
    rationale: z.string().min(1).max(2048),
  })
  .strict();

export const proposalRevisionSchema = z
  .object({
    schemaVersion: schemaVersionCheck(PROPOSAL_REVISION_SCHEMA_VERSION),
    id: z.string().min(1).max(64),
    proposalId: proposalIdSchema,
    incidentId: incidentIdSchema,
    sessionId: agentSessionIdSchema,
    taskId: agentTaskIdSchema,
    revisionNumber: z.number().int().min(1),
    responseOptions: z.array(responseOptionSchema).min(1),
    selectedOptionId: z.string().min(1).max(64),
    rationale: z.string().min(1).max(4096),
    riskTradeoffs: z.string().min(1).max(4096),
    linkedHypothesisIds: z.array(hypothesisIdSchema).default([]),
    createdAt: utcTimestampSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const optionIds = new Set(value.responseOptions.map((option) => option.optionId));
    if (!optionIds.has(value.selectedOptionId)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'selectedOptionId must reference a response option',
      });
    }
  });

export const approvalRequirementSchema = z
  .object({
    schemaVersion: schemaVersionCheck(APPROVAL_REQUIREMENT_SCHEMA_VERSION),
    required: z.boolean(),
    approverRoles: z.array(z.string()).default([]),
    rationale: z.string().min(1).max(2048),
  })
  .strict();

export const policyInputSchema = z
  .object({
    schemaVersion: schemaVersionCheck(POLICY_INPUT_SCHEMA_VERSION),
    proposalId: proposalIdSchema,
    proposalRevisionId: z.string().min(1).max(64),
    proposalRevisionNumber: z.number().int().min(1),
    currentRevisionId: z.string().min(1).max(64),
    actionClass: z.enum(['class_0', 'class_1', 'class_2', 'class_3']),
    scenarioCommand: scenarioCommandTemplateSchema,
    agentRole: z.enum(['WATCHTOWER', 'TRACE', 'ORACLE', 'BASTION', 'WARDEN', 'SCRIBE']),
    targetAssetId: assetIdSchema,
    assetCriticality: z.number().min(0).max(1),
    reversibility: z.string().min(1).max(1024),
    incidentState: z.enum([
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
    scenarioRestricted: z.boolean().default(false),
    hypothesisConfidenceMin: z.number().min(0).max(1).nullable().optional(),
  })
  .strict();

export const policyDecisionSchema = z
  .object({
    schemaVersion: schemaVersionCheck(POLICY_DECISION_SCHEMA_VERSION),
    id: z.string().min(1).max(64),
    proposalId: proposalIdSchema,
    proposalRevisionId: z.string().min(1).max(64),
    incidentId: incidentIdSchema,
    sessionId: agentSessionIdSchema,
    taskId: agentTaskIdSchema,
    outcome: policyOutcomeSchema,
    reasonCodes: z.array(policyReasonCodeSchema).min(1),
    approvalRequirement: approvalRequirementSchema.nullable().optional(),
    policyInput: policyInputSchema,
    explanationProse: z.string().max(4096).default(''),
    evaluatedAt: utcTimestampSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.outcome === 'approval_required' && value.approvalRequirement == null) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'approval_required decisions must include approvalRequirement',
      });
    }
  });

export const triggerBastionRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(TRIGGER_BASTION_REQUEST_SCHEMA_VERSION),
    runId: runIdSchema,
    incidentId: incidentIdSchema.nullable().optional(),
    traceId: traceIdSchema,
    providerId: z.string().default('mock'),
    idempotencyKey: z.string().min(1).max(256),
  })
  .strict();

export const triggerWardenRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(TRIGGER_WARDEN_REQUEST_SCHEMA_VERSION),
    runId: runIdSchema,
    incidentId: incidentIdSchema.nullable().optional(),
    proposalId: proposalIdSchema.nullable().optional(),
    traceId: traceIdSchema,
    providerId: z.string().default('mock'),
    idempotencyKey: z.string().min(1).max(256),
  })
  .strict();

export type ScenarioCommandTemplateV1 = z.infer<typeof scenarioCommandTemplateSchema>;
export type PolicyOutcomeV1 = z.infer<typeof policyOutcomeSchema>;
export type PolicyReasonCodeV1 = z.infer<typeof policyReasonCodeSchema>;
export type ResponseOptionV1 = z.infer<typeof responseOptionSchema>;
export type ProposalRevisionV1 = z.infer<typeof proposalRevisionSchema>;
export type ApprovalRequirementV1 = z.infer<typeof approvalRequirementSchema>;
export type PolicyInputV1 = z.infer<typeof policyInputSchema>;
export type PolicyDecisionV1 = z.infer<typeof policyDecisionSchema>;
export type TriggerBastionRequestV1 = z.infer<typeof triggerBastionRequestSchema>;
export type TriggerWardenRequestV1 = z.infer<typeof triggerWardenRequestSchema>;

/** Phase 24 approval workflow contracts. */

import { z } from 'zod';

import { approvalSchema, executedActionSchema } from './entities';
import {
  approvalIdSchema,
  eventIdSchema,
  proposalIdSchema,
  revisionSchema,
  runIdSchema,
  utcTimestampSchema,
} from './primitives';
import {
  policyDecisionSchema,
  policyOutcomeSchema,
  responseOptionSchema,
  scenarioCommandTemplateSchema,
} from './proposals';
import {
  APPROVE_PROPOSAL_REQUEST_SCHEMA_VERSION,
  APPROVE_PROPOSAL_RESPONSE_SCHEMA_VERSION,
  AUTHORIZED_SIMULATION_COMMAND_SCHEMA_VERSION,
  CANCEL_PROPOSAL_REQUEST_SCHEMA_VERSION,
  EXECUTION_RESULT_SCHEMA_VERSION,
  FINAL_POLICY_CHECK_SCHEMA_VERSION,
  MODIFY_PROPOSAL_REQUEST_SCHEMA_VERSION,
  MODIFY_PROPOSAL_RESPONSE_SCHEMA_VERSION,
  PROPOSAL_MODIFICATION_SCHEMA_VERSION,
  REJECT_PROPOSAL_REQUEST_SCHEMA_VERSION,
  REJECT_PROPOSAL_RESPONSE_SCHEMA_VERSION,
  STALE_PROPOSAL_ERROR_SCHEMA_VERSION,
} from './versioning';

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .refine((v) => v === expected);

export const approvalErrorCodeSchema = z.enum([
  'STALE_PROPOSAL',
  'UNAUTHORIZED',
  'POLICY_BLOCKED',
  'VALIDATION_FAILED',
  'CONFLICT',
  'NOT_FOUND',
  'ALREADY_DECIDED',
  'EXECUTION_FAILED',
]);

export const staleProposalErrorSchema = z
  .object({
    schemaVersion: schemaVersionCheck(STALE_PROPOSAL_ERROR_SCHEMA_VERSION),
    code: approvalErrorCodeSchema.default('STALE_PROPOSAL'),
    message: z.string().min(1).max(1024),
    proposalId: proposalIdSchema,
    expectedRevisionId: z.string().min(1).max(64).nullable().optional(),
    actualRevisionId: z.string().min(1).max(64).nullable().optional(),
    expectedRevision: revisionSchema.nullable().optional(),
    actualRevision: revisionSchema.nullable().optional(),
    details: z.record(z.string(), z.unknown()).default({}),
  })
  .strict();

export const proposalModificationSchema = z
  .object({
    schemaVersion: schemaVersionCheck(PROPOSAL_MODIFICATION_SCHEMA_VERSION),
    proposalId: proposalIdSchema,
    previousRevisionId: z.string().min(1).max(64),
    newRevisionId: z.string().min(1).max(64),
    selectedOptionId: z.string().min(1).max(64),
    responseOptions: z.array(responseOptionSchema).nullable().optional(),
    rationale: z.string().min(1).max(4096),
    riskTradeoffs: z.string().min(1).max(4096),
    comment: z.string().max(2048).default(''),
    modifiedBy: z.string().min(1).max(128),
    modifiedAt: utcTimestampSchema,
  })
  .strict();

export const finalPolicyCheckSchema = z
  .object({
    schemaVersion: schemaVersionCheck(FINAL_POLICY_CHECK_SCHEMA_VERSION),
    proposalId: proposalIdSchema,
    proposalRevisionId: z.string().min(1).max(64),
    currentRevisionId: z.string().min(1).max(64),
    outcome: policyOutcomeSchema,
    decision: policyDecisionSchema,
    executable: z.boolean(),
    checkedAt: utcTimestampSchema,
  })
  .strict();

export const authorizedSimulationCommandSchema = z
  .object({
    schemaVersion: schemaVersionCheck(AUTHORIZED_SIMULATION_COMMAND_SCHEMA_VERSION),
    proposalId: proposalIdSchema,
    approvalId: approvalIdSchema,
    runId: runIdSchema,
    scenarioCommand: scenarioCommandTemplateSchema,
    pluginId: z.string().min(1).max(128),
    targetAssetId: z.string().min(1).max(128),
    config: z.record(z.string(), z.unknown()).default({}),
    commandId: z.string().min(1).max(256),
    authorizationToken: z.string().min(1).max(256),
    actorId: z.string().min(1).max(128),
  })
  .strict();

export const executionResultSchema = z
  .object({
    schemaVersion: schemaVersionCheck(EXECUTION_RESULT_SCHEMA_VERSION),
    executedAction: executedActionSchema,
    resultEventId: eventIdSchema,
    commandId: z.string().min(1).max(256),
    success: z.boolean(),
    replayed: z.boolean().default(false),
    message: z.string().max(1024).default(''),
  })
  .strict();

export const approveProposalRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(APPROVE_PROPOSAL_REQUEST_SCHEMA_VERSION),
    proposalId: proposalIdSchema,
    expectedRevisionId: z.string().min(1).max(64),
    expectedRevision: revisionSchema,
    comment: z.string().max(2048).default(''),
    idempotencyKey: z.string().min(1).max(256),
    actorId: z.string().max(128).nullable().optional(),
  })
  .strict();

export const rejectProposalRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(REJECT_PROPOSAL_REQUEST_SCHEMA_VERSION),
    proposalId: proposalIdSchema,
    expectedRevisionId: z.string().min(1).max(64),
    expectedRevision: revisionSchema,
    reason: z.string().min(1).max(2048),
    comment: z.string().max(2048).default(''),
    idempotencyKey: z.string().min(1).max(256),
    actorId: z.string().max(128).nullable().optional(),
  })
  .strict();

export const modifyProposalRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(MODIFY_PROPOSAL_REQUEST_SCHEMA_VERSION),
    proposalId: proposalIdSchema,
    expectedRevisionId: z.string().min(1).max(64),
    expectedRevision: revisionSchema,
    selectedOptionId: z.string().min(1).max(64),
    responseOptions: z.array(responseOptionSchema).nullable().optional(),
    rationale: z.string().min(1).max(4096),
    riskTradeoffs: z.string().min(1).max(4096),
    comment: z.string().max(2048).default(''),
    idempotencyKey: z.string().min(1).max(256),
    actorId: z.string().max(128).nullable().optional(),
  })
  .strict();

export const cancelProposalRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(CANCEL_PROPOSAL_REQUEST_SCHEMA_VERSION),
    proposalId: proposalIdSchema,
    expectedRevisionId: z.string().min(1).max(64),
    expectedRevision: revisionSchema,
    reason: z.string().min(1).max(2048),
    idempotencyKey: z.string().min(1).max(256),
    actorId: z.string().max(128).nullable().optional(),
  })
  .strict();

export const approveProposalResponseSchema = z
  .object({
    schemaVersion: schemaVersionCheck(APPROVE_PROPOSAL_RESPONSE_SCHEMA_VERSION),
    approval: approvalSchema,
    finalPolicyCheck: finalPolicyCheckSchema,
    execution: executionResultSchema.nullable().optional(),
    proposalStatus: z.enum(['pending', 'approved', 'rejected', 'executed', 'cancelled']),
    replayed: z.boolean().default(false),
  })
  .strict();

export const rejectProposalResponseSchema = z
  .object({
    schemaVersion: schemaVersionCheck(REJECT_PROPOSAL_RESPONSE_SCHEMA_VERSION),
    approval: approvalSchema,
    proposalStatus: z.enum(['pending', 'approved', 'rejected', 'executed', 'cancelled']),
    replayed: z.boolean().default(false),
  })
  .strict();

export const modifyProposalResponseSchema = z
  .object({
    schemaVersion: schemaVersionCheck(MODIFY_PROPOSAL_RESPONSE_SCHEMA_VERSION),
    modification: proposalModificationSchema,
    policyDecision: policyDecisionSchema,
    proposalStatus: z.enum(['pending', 'approved', 'rejected', 'executed', 'cancelled']),
    replayed: z.boolean().default(false),
  })
  .strict();

export type ApprovalErrorCode = z.infer<typeof approvalErrorCodeSchema>;
export type StaleProposalErrorV1 = z.infer<typeof staleProposalErrorSchema>;
export type ProposalModificationV1 = z.infer<typeof proposalModificationSchema>;
export type FinalPolicyCheckV1 = z.infer<typeof finalPolicyCheckSchema>;
export type AuthorizedSimulationCommandV1 = z.infer<typeof authorizedSimulationCommandSchema>;
export type ExecutionResultV1 = z.infer<typeof executionResultSchema>;
export type ApproveProposalRequestV1 = z.infer<typeof approveProposalRequestSchema>;
export type RejectProposalRequestV1 = z.infer<typeof rejectProposalRequestSchema>;
export type ModifyProposalRequestV1 = z.infer<typeof modifyProposalRequestSchema>;
export type CancelProposalRequestV1 = z.infer<typeof cancelProposalRequestSchema>;
export type ApproveProposalResponseV1 = z.infer<typeof approveProposalResponseSchema>;
export type RejectProposalResponseV1 = z.infer<typeof rejectProposalResponseSchema>;
export type ModifyProposalResponseV1 = z.infer<typeof modifyProposalResponseSchema>;

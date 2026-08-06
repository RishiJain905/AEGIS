import { z } from 'zod';

import { agentSessionSchema, autonomyInitiatorSchema } from './entities';
import {
  agentArtifactIdSchema,
  agentSessionIdSchema,
  agentTaskIdSchema,
  citableEvidenceIdSchema,
  generationRequestIdSchema,
  incidentIdSchema,
  runIdSchema,
  toolInvocationIdSchema,
  traceIdSchema,
  utcTimestampSchema,
} from './primitives';

// Upper bound on the operator free-text directive threaded into a task prompt.
export const MAX_OPERATOR_INSTRUCTIONS_LENGTH = 4000;
import {
  AGENT_ARTIFACT_SCHEMA_VERSION,
  AGENT_BUDGET_SCHEMA_VERSION,
  AGENT_DEFINITION_SCHEMA_VERSION,
  AGENT_SESSION_DETAIL_SCHEMA_VERSION,
  AGENT_STATE_TRANSITION_SCHEMA_VERSION,
  AGENT_TASK_SCHEMA_VERSION,
  CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
  CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
  EVIDENCE_CITATION_SCHEMA_VERSION,
  TOOL_DEFINITION_SCHEMA_VERSION,
  TOOL_INVOCATION_SCHEMA_VERSION,
  TOOL_RESULT_SCHEMA_VERSION,
} from './versioning';

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .refine((v) => v === expected);

export const AgentTaskStatus = {
  QUEUED: 'queued',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
  TIMED_OUT: 'timed_out',
} as const;

export const AgentToolClass = {
  READ: 'read',
  ANALYSIS_WRITE: 'analysis_write',
  PROPOSAL: 'proposal',
  EXECUTION: 'execution',
} as const;

export const ToolInvocationStatus = {
  SUCCESS: 'success',
  FAILED: 'failed',
  REJECTED: 'rejected',
} as const;

export const AgentArtifactType = {
  STEP_RESULT: 'step_result',
  HYPOTHESIS: 'hypothesis',
  PROPOSAL: 'proposal',
  AUDIT: 'audit',
} as const;

export const agentBudgetSchema = z
  .object({
    schemaVersion: schemaVersionCheck(AGENT_BUDGET_SCHEMA_VERSION),
    maxTokens: z.number().int().min(1),
    maxLatencyMs: z.number().int().min(1),
    maxCostUsd: z.number().min(0),
    consumedTokens: z.number().int().min(0).default(0),
    consumedLatencyMs: z.number().int().min(0).default(0),
    consumedCostUsd: z.number().min(0).default(0),
  })
  .strict();

export const agentDefinitionSchema = z
  .object({
    schemaVersion: schemaVersionCheck(AGENT_DEFINITION_SCHEMA_VERSION),
    role: z.enum(['WATCHTOWER', 'TRACE', 'ORACLE', 'BASTION', 'WARDEN', 'SCRIBE']),
    definitionId: z.string().min(1).max(128),
    promptVersion: z.string().min(1).max(64),
    providerId: z.string().min(1).max(64),
    modelId: z.string().min(1).max(128),
    allowedTools: z.array(z.string()),
    defaultBudget: agentBudgetSchema,
  })
  .strict();

export const toolDefinitionSchema = z
  .object({
    schemaVersion: schemaVersionCheck(TOOL_DEFINITION_SCHEMA_VERSION),
    name: z.string().min(1).max(128),
    description: z.string().min(1).max(2048),
    toolClass: z.enum(['read', 'analysis_write', 'proposal', 'execution']),
    modelVisible: z.boolean(),
    inputSchema: z.record(z.unknown()).default({}),
    outputSchema: z.record(z.unknown()).default({}),
    allowedRoles: z.array(z.enum(['WATCHTOWER', 'TRACE', 'ORACLE', 'BASTION', 'WARDEN', 'SCRIBE'])),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.toolClass === 'execution' && value.modelVisible) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Execution-class tools must not be model-visible',
      });
    }
  });

export const evidenceCitationSchema = z
  .object({
    schemaVersion: schemaVersionCheck(EVIDENCE_CITATION_SCHEMA_VERSION),
    // An authored evidence id or a run event id — the catalogue is the run's
    // event pool, so the operator can verify either in the Evidence tab.
    evidenceId: citableEvidenceIdSchema,
    rationale: z.string().default(''),
  })
  .strict();

export const agentTaskSchema = z
  .object({
    schemaVersion: schemaVersionCheck(AGENT_TASK_SCHEMA_VERSION),
    id: agentTaskIdSchema,
    sessionId: agentSessionIdSchema,
    runId: runIdSchema,
    incidentId: incidentIdSchema.nullable().default(null),
    status: z.enum(['queued', 'running', 'completed', 'failed', 'cancelled', 'timed_out']),
    attempt: z.number().int().min(1).default(1),
    idempotencyKey: z.string().min(1).max(256),
    traceId: traceIdSchema,
    providerId: z.string().min(1).max(64),
    instructions: z.string().max(MAX_OPERATOR_INSTRUCTIONS_LENGTH).nullable().optional(),
    // Phase 7: who originated the task ("operator" default, "autonomy" for the
    // event-driven triage loop). Additive optional field.
    initiator: autonomyInitiatorSchema.default('operator'),
    errorCode: z.string().nullable().optional(),
    errorMessage: z.string().nullable().optional(),
    createdAt: utcTimestampSchema,
    updatedAt: utcTimestampSchema,
    startedAt: utcTimestampSchema.nullable().optional(),
    completedAt: utcTimestampSchema.nullable().optional(),
  })
  .strict();

export const agentStateTransitionSchema = z
  .object({
    schemaVersion: schemaVersionCheck(AGENT_STATE_TRANSITION_SCHEMA_VERSION),
    id: z.string().min(1).max(64),
    sessionId: agentSessionIdSchema,
    taskId: agentTaskIdSchema.nullable().optional(),
    fromState: z.enum([
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
    toState: z.enum([
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
    reason: z.string().min(1).max(512),
    createdAt: utcTimestampSchema,
  })
  .strict();

export const toolInvocationSchema = z
  .object({
    schemaVersion: schemaVersionCheck(TOOL_INVOCATION_SCHEMA_VERSION),
    id: toolInvocationIdSchema,
    taskId: agentTaskIdSchema,
    sessionId: agentSessionIdSchema,
    toolName: z.string().min(1).max(128),
    toolClass: z.enum(['read', 'analysis_write', 'proposal', 'execution']),
    status: z.enum(['success', 'failed', 'rejected']),
    durationMs: z.number().int().min(0),
    input: z.record(z.unknown()).default({}),
    output: z.record(z.unknown()).nullable().optional(),
    errorCode: z.string().nullable().optional(),
    errorMessage: z.string().nullable().optional(),
    /**
     * Which round of the agent's multi-turn tool loop ran this call (1-based).
     * Null/absent means it was not part of the loop: it came from the model's
     * final answer and ran once, after it.
     */
    loopIteration: z.number().int().min(1).nullable().optional(),
    createdAt: utcTimestampSchema,
  })
  .strict();

export const toolResultSchema = z
  .object({
    schemaVersion: schemaVersionCheck(TOOL_RESULT_SCHEMA_VERSION),
    invocationId: toolInvocationIdSchema,
    status: z.enum(['success', 'failed', 'rejected']),
    output: z.record(z.unknown()).nullable().optional(),
    errorCode: z.string().nullable().optional(),
    errorMessage: z.string().nullable().optional(),
  })
  .strict();

export const agentArtifactSchema = z
  .object({
    schemaVersion: schemaVersionCheck(AGENT_ARTIFACT_SCHEMA_VERSION),
    id: agentArtifactIdSchema,
    taskId: agentTaskIdSchema,
    sessionId: agentSessionIdSchema,
    artifactType: z.enum(['step_result', 'hypothesis', 'proposal', 'audit']),
    payload: z.record(z.unknown()).default({}),
    generationArtifactId: generationRequestIdSchema.nullable().optional(),
    createdAt: utcTimestampSchema,
  })
  .strict();

export const createAgentSessionRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION),
    role: z.enum(['WATCHTOWER', 'TRACE', 'ORACLE', 'BASTION', 'WARDEN', 'SCRIBE']),
    traceId: traceIdSchema,
    enqueueInitialTask: z.boolean().default(true),
    providerId: z.string().nullable().optional(),
    instructions: z.string().max(MAX_OPERATOR_INSTRUCTIONS_LENGTH).nullable().optional(),
  })
  .strict();

export const createAgentTaskRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION),
    idempotencyKey: z.string().min(1).max(256),
    providerId: z.string().nullable().optional(),
    instructions: z.string().max(MAX_OPERATOR_INSTRUCTIONS_LENGTH).nullable().optional(),
    // Phase 7: task origin. Defaults to "operator"; the autonomy loop passes "autonomy".
    initiator: autonomyInitiatorSchema.default('operator'),
  })
  .strict();

export const agentSessionDetailSchema = z
  .object({
    schemaVersion: schemaVersionCheck(AGENT_SESSION_DETAIL_SCHEMA_VERSION),
    session: agentSessionSchema,
    tasks: z.array(agentTaskSchema).default([]),
    transitions: z.array(agentStateTransitionSchema).default([]),
    toolInvocations: z.array(toolInvocationSchema).default([]),
    artifacts: z.array(agentArtifactSchema).default([]),
    budget: agentBudgetSchema.nullable().optional(),
  })
  .strict();

export type AgentBudgetV1 = z.infer<typeof agentBudgetSchema>;
export type AgentDefinitionV1 = z.infer<typeof agentDefinitionSchema>;
export type ToolDefinitionV1 = z.infer<typeof toolDefinitionSchema>;
export type EvidenceCitationV1 = z.infer<typeof evidenceCitationSchema>;
export type AgentTaskV1 = z.infer<typeof agentTaskSchema>;
export type AgentStateTransitionV1 = z.infer<typeof agentStateTransitionSchema>;
export type ToolInvocationV1 = z.infer<typeof toolInvocationSchema>;
export type ToolResultV1 = z.infer<typeof toolResultSchema>;
export type AgentArtifactV1 = z.infer<typeof agentArtifactSchema>;
export type CreateAgentSessionRequestV1 = z.infer<typeof createAgentSessionRequestSchema>;
export type CreateAgentTaskRequestV1 = z.infer<typeof createAgentTaskRequestSchema>;
export type AgentSessionDetailV1 = z.infer<typeof agentSessionDetailSchema>;

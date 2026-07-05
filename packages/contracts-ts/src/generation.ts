import { z } from 'zod';

import {
  correlationIdSchema,
  generationRequestIdSchema,
  traceIdSchema,
  utcTimestampSchema,
} from './primitives';
import {
  GENERATION_ARTIFACT_SCHEMA_VERSION,
  GENERATION_REQUEST_SCHEMA_VERSION,
  GENERATION_RESPONSE_SCHEMA_VERSION,
  MODEL_CONFIG_SCHEMA_VERSION,
  PROVIDER_CAPABILITIES_SCHEMA_VERSION,
  PROVIDER_ERROR_SCHEMA_VERSION,
  PROVIDER_GENERATE_REQUEST_SCHEMA_VERSION,
  PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION,
  PROVIDER_USAGE_SCHEMA_VERSION,
  RECORDED_RESPONSE_KEY_SCHEMA_VERSION,
  STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
  TOOL_SCHEMA_SCHEMA_VERSION,
} from './versioning';

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .refine((v) => v === expected);

export const GenerationMessageRole = {
  SYSTEM: 'system',
  USER: 'user',
  ASSISTANT: 'assistant',
  TOOL: 'tool',
} as const;

export const ProviderCapability = {
  STRUCTURED_OUTPUT: 'structured_output',
  TOOLS: 'tools',
  VISION: 'vision',
  STREAMING: 'streaming',
} as const;

export const ProviderFinishReason = {
  STOP: 'stop',
  LENGTH: 'length',
  TOOL_CALLS: 'tool_calls',
  CONTENT_FILTER: 'content_filter',
  ERROR: 'error',
} as const;

export const ProviderErrorCode = {
  VALIDATION_FAILED: 'VALIDATION_FAILED',
  CAPABILITY_UNSUPPORTED: 'CAPABILITY_UNSUPPORTED',
  CREDENTIALS_MISSING: 'CREDENTIALS_MISSING',
  OUTPUT_LIMIT_EXCEEDED: 'OUTPUT_LIMIT_EXCEEDED',
  STRUCTURED_OUTPUT_INVALID: 'STRUCTURED_OUTPUT_INVALID',
  TIMEOUT: 'TIMEOUT',
  RETRY_EXHAUSTED: 'RETRY_EXHAUSTED',
  CIRCUIT_OPEN: 'CIRCUIT_OPEN',
  PROVIDER_UNAVAILABLE: 'PROVIDER_UNAVAILABLE',
  CANCELLATION: 'CANCELLATION',
  INTERNAL: 'INTERNAL',
} as const;

export const generationMessageSchema = z.object({
  role: z.enum([
    GenerationMessageRole.SYSTEM,
    GenerationMessageRole.USER,
    GenerationMessageRole.ASSISTANT,
    GenerationMessageRole.TOOL,
  ]),
  content: z.string().min(0).max(65536),
  name: z.string().max(128).optional(),
});

export const toolSchemaSchema = z.object({
  schemaVersion: schemaVersionCheck(TOOL_SCHEMA_SCHEMA_VERSION),
  name: z.string().min(1).max(128),
  description: z.string().min(1).max(2048),
  parameters: z.record(z.unknown()).default({}),
});

export const structuredOutputSpecSchema = z.object({
  schemaVersion: schemaVersionCheck(STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION),
  jsonSchema: z.record(z.unknown()),
  strict: z.boolean().default(true),
  maxRepairAttempts: z.number().int().min(0).max(2).default(1),
});

export const providerCapabilitiesSchema = z.object({
  schemaVersion: schemaVersionCheck(PROVIDER_CAPABILITIES_SCHEMA_VERSION),
  capabilities: z
    .array(
      z.enum([
        ProviderCapability.STRUCTURED_OUTPUT,
        ProviderCapability.TOOLS,
        ProviderCapability.VISION,
        ProviderCapability.STREAMING,
      ]),
    )
    .default([]),
});

export const modelConfigSchema = z.object({
  schemaVersion: schemaVersionCheck(MODEL_CONFIG_SCHEMA_VERSION),
  providerId: z.string().min(1).max(64),
  modelId: z.string().min(1).max(128),
  promptVersion: z.string().min(1).max(64),
  temperature: z.number().min(0).max(2).optional(),
  maxOutputTokens: z.number().int().min(1).max(65536).optional(),
});

export const providerUsageSchema = z
  .object({
    schemaVersion: schemaVersionCheck(PROVIDER_USAGE_SCHEMA_VERSION),
    promptTokens: z.number().int().min(0),
    completionTokens: z.number().int().min(0),
    totalTokens: z.number().int().min(0),
    estimatedCostUsd: z.number().min(0).optional(),
  })
  .superRefine((value, ctx) => {
    if (value.totalTokens !== value.promptTokens + value.completionTokens) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'totalTokens must equal promptTokens + completionTokens',
      });
    }
  });

export const providerErrorSchema = z.object({
  schemaVersion: schemaVersionCheck(PROVIDER_ERROR_SCHEMA_VERSION),
  code: z.enum([
    ProviderErrorCode.VALIDATION_FAILED,
    ProviderErrorCode.CAPABILITY_UNSUPPORTED,
    ProviderErrorCode.CREDENTIALS_MISSING,
    ProviderErrorCode.OUTPUT_LIMIT_EXCEEDED,
    ProviderErrorCode.STRUCTURED_OUTPUT_INVALID,
    ProviderErrorCode.TIMEOUT,
    ProviderErrorCode.RETRY_EXHAUSTED,
    ProviderErrorCode.CIRCUIT_OPEN,
    ProviderErrorCode.PROVIDER_UNAVAILABLE,
    ProviderErrorCode.CANCELLATION,
    ProviderErrorCode.INTERNAL,
  ]),
  message: z.string().min(1).max(2048),
  retryable: z.boolean().default(false),
  details: z.record(z.unknown()).default({}),
  traceId: traceIdSchema.optional(),
});

export const recordedResponseKeySchema = z.object({
  schemaVersion: schemaVersionCheck(RECORDED_RESPONSE_KEY_SCHEMA_VERSION),
  providerId: z.string().min(1).max(64),
  modelId: z.string().min(1).max(128),
  promptVersion: z.string().min(1).max(64),
  requestHash: z.string().min(8).max(128),
});

export const generationRequestSchema = z.object({
  schemaVersion: schemaVersionCheck(GENERATION_REQUEST_SCHEMA_VERSION),
  requestId: generationRequestIdSchema,
  traceId: traceIdSchema,
  correlationId: correlationIdSchema.optional(),
  providerId: z.string().max(64).optional(),
  modelConfig: modelConfigSchema,
  messages: z.array(generationMessageSchema).min(1).max(64),
  tools: z.array(toolSchemaSchema).max(32).default([]),
  structuredOutput: structuredOutputSpecSchema.optional(),
  capabilitiesRequired: z
    .array(
      z.enum([
        ProviderCapability.STRUCTURED_OUTPUT,
        ProviderCapability.TOOLS,
        ProviderCapability.VISION,
        ProviderCapability.STREAMING,
      ]),
    )
    .default([]),
  maxOutputTokens: z.number().int().min(1).max(65536).default(4096),
  timeoutMs: z.number().int().min(100).max(600000).optional(),
  idempotencyKey: z.string().max(256).optional(),
});

export const generationResponseSchema = z.object({
  schemaVersion: schemaVersionCheck(GENERATION_RESPONSE_SCHEMA_VERSION),
  requestId: generationRequestIdSchema,
  traceId: traceIdSchema,
  providerId: z.string().min(1).max(64),
  modelId: z.string().min(1).max(128),
  promptVersion: z.string().min(1).max(64),
  content: z.string().max(65536).optional(),
  structuredData: z.record(z.unknown()).optional(),
  finishReason: z.enum([
    ProviderFinishReason.STOP,
    ProviderFinishReason.LENGTH,
    ProviderFinishReason.TOOL_CALLS,
    ProviderFinishReason.CONTENT_FILTER,
    ProviderFinishReason.ERROR,
  ]),
  usage: providerUsageSchema,
  latencyMs: z.number().int().min(0),
  artifactRef: z.string().max(512).optional(),
  completedAt: utcTimestampSchema,
});

export const generationArtifactSchema = z.object({
  schemaVersion: schemaVersionCheck(GENERATION_ARTIFACT_SCHEMA_VERSION),
  requestId: generationRequestIdSchema,
  traceId: traceIdSchema,
  providerId: z.string().min(1).max(64),
  modelId: z.string().min(1).max(128),
  promptVersion: z.string().min(1).max(64),
  latencyMs: z.number().int().min(0),
  usage: providerUsageSchema.optional(),
  error: providerErrorSchema.optional(),
  sanitizedRequest: z.record(z.unknown()),
  sanitizedResponse: z.record(z.unknown()).optional(),
  objectStorageRef: z.string().max(512).optional(),
  recordedAt: utcTimestampSchema,
});

export const providerGenerateRequestSchema = z.object({
  schemaVersion: schemaVersionCheck(PROVIDER_GENERATE_REQUEST_SCHEMA_VERSION),
  request: generationRequestSchema,
  providerId: z.string().max(64).optional(),
  dryRun: z.boolean().default(false),
});

export const providerGenerateResponseSchema = z
  .object({
    schemaVersion: schemaVersionCheck(PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION),
    response: generationResponseSchema.optional(),
    error: providerErrorSchema.optional(),
  })
  .superRefine((value, ctx) => {
    if ((value.response === undefined) === (value.error === undefined)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Exactly one of response or error must be set',
      });
    }
  });

export type GenerationMessageV1 = z.infer<typeof generationMessageSchema>;
export type ToolSchemaV1 = z.infer<typeof toolSchemaSchema>;
export type StructuredOutputSpecV1 = z.infer<typeof structuredOutputSpecSchema>;
export type ProviderCapabilitiesV1 = z.infer<typeof providerCapabilitiesSchema>;
export type ModelConfigV1 = z.infer<typeof modelConfigSchema>;
export type ProviderUsageV1 = z.infer<typeof providerUsageSchema>;
export type ProviderErrorV1 = z.infer<typeof providerErrorSchema>;
export type RecordedResponseKeyV1 = z.infer<typeof recordedResponseKeySchema>;
export type GenerationRequestV1 = z.infer<typeof generationRequestSchema>;
export type GenerationResponseV1 = z.infer<typeof generationResponseSchema>;
export type GenerationArtifactV1 = z.infer<typeof generationArtifactSchema>;
export type ProviderGenerateRequestV1 = z.infer<typeof providerGenerateRequestSchema>;
export type ProviderGenerateResponseV1 = z.infer<typeof providerGenerateResponseSchema>;

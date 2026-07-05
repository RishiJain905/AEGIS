import { z } from 'zod';

import { ContractErrorCode, ContractValidationError } from './errors';
import { SUPPORTED_SCHEMA_VERSIONS } from './versioning';

const AUTHORED_ID_PATTERN =
  /^(asset|incident|alert|evidence|agent-session|business-unit|edge|scenario|scenario-version|relationship|service|user|device|identity|database|control):[a-z0-9][a-z0-9._-]{0,126}$/;

const RUNTIME_ID_PATTERN =
  /^(evt|run|trc|inc|alt|evd|ags|prp|apr|act|mdl|scr|hyp|gen)_[0-9A-HJKMNP-TV-Z]{26}$/;

const UTC_TIMESTAMP_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;

export function validateAuthoredId(value: string): string {
  if (!AUTHORED_ID_PATTERN.test(value)) {
    throw new ContractValidationError({
      code: ContractErrorCode.INVALID_IDENTIFIER,
      message: `Invalid authored identifier: ${value}`,
      details: { value },
    });
  }
  return value;
}

export function validateRuntimeId(prefix: string, value: string): string {
  if (!RUNTIME_ID_PATTERN.test(value) || !value.startsWith(`${prefix}_`)) {
    throw new ContractValidationError({
      code: ContractErrorCode.INVALID_IDENTIFIER,
      message: `Invalid runtime identifier: ${value}`,
      details: { value, expectedPrefix: prefix },
    });
  }
  return value;
}

export const authoredIdSchema = z.string().superRefine((value, ctx) => {
  try {
    validateAuthoredId(value);
  } catch (error) {
    if (error instanceof ContractValidationError) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: error.message });
    }
  }
});

export const assetIdSchema = authoredIdSchema;
export const incidentIdSchema = authoredIdSchema;
export const alertIdSchema = authoredIdSchema;
export const evidenceIdSchema = authoredIdSchema;
export const agentSessionIdSchema = authoredIdSchema;
export const scenarioIdSchema = authoredIdSchema;
export const clusterIdSchema = authoredIdSchema;
export const edgeIdSchema = authoredIdSchema;

export const eventIdSchema = z.string().superRefine((value, ctx) => {
  try {
    validateRuntimeId('evt', value);
  } catch (error) {
    if (error instanceof ContractValidationError) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: error.message });
    }
  }
});

export const runIdSchema = z.string().superRefine((value, ctx) => {
  try {
    validateRuntimeId('run', value);
  } catch (error) {
    if (error instanceof ContractValidationError) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: error.message });
    }
  }
});

export const traceIdSchema = z.string().superRefine((value, ctx) => {
  try {
    validateRuntimeId('trc', value);
  } catch (error) {
    if (error instanceof ContractValidationError) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: error.message });
    }
  }
});

export const causationIdSchema = eventIdSchema;
export const correlationIdSchema = traceIdSchema;
export const proposalIdSchema = z.string().superRefine((value, ctx) => {
  try {
    validateRuntimeId('prp', value);
  } catch (error) {
    if (error instanceof ContractValidationError) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: error.message });
    }
  }
});
export const approvalIdSchema = z.string().superRefine((value, ctx) => {
  try {
    validateRuntimeId('apr', value);
  } catch (error) {
    if (error instanceof ContractValidationError) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: error.message });
    }
  }
});
export const actionIdSchema = z.string().superRefine((value, ctx) => {
  try {
    validateRuntimeId('act', value);
  } catch (error) {
    if (error instanceof ContractValidationError) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: error.message });
    }
  }
});
export const modelIdSchema = z.string().superRefine((value, ctx) => {
  try {
    validateRuntimeId('mdl', value);
  } catch (error) {
    if (error instanceof ContractValidationError) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: error.message });
    }
  }
});
export const hypothesisIdSchema = z.string().superRefine((value, ctx) => {
  try {
    validateRuntimeId('hyp', value);
  } catch (error) {
    if (error instanceof ContractValidationError) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: error.message });
    }
  }
});
export const generationRequestIdSchema = z.string().superRefine((value, ctx) => {
  try {
    validateRuntimeId('gen', value);
  } catch (error) {
    if (error instanceof ContractValidationError) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: error.message });
    }
  }
});

export const utcTimestampSchema = z.string().superRefine((value, ctx) => {
  if (!UTC_TIMESTAMP_PATTERN.test(value)) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: `Invalid UTC timestamp: ${value}`,
    });
    return;
  }
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: `Invalid UTC timestamp: ${value}`,
    });
  }
});

export const simTimestampSchema = utcTimestampSchema;
export const sequenceSchema = z.number().int().min(0);
export const revisionSchema = z.number().int().min(0);

export function assertSupportedSchemaVersion(
  contractName: string,
  schemaVersion: number,
  traceId?: string,
): void {
  const supported = SUPPORTED_SCHEMA_VERSIONS[contractName];
  if (!supported) {
    throw new ContractValidationError({
      code: ContractErrorCode.VALIDATION_FAILED,
      message: `Unknown contract name: ${contractName}`,
      details: { contractName },
      traceId,
    });
  }
  if (!supported.includes(schemaVersion)) {
    throw new ContractValidationError({
      code: ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
      message: `Unsupported schema version ${String(schemaVersion)} for contract ${contractName}`,
      details: {
        contractName,
        schemaVersion,
        supportedVersions: supported,
      },
      traceId,
    });
  }
}

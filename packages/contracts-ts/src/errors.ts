import { z } from 'zod';

export const ContractErrorCode = {
  SCHEMA_VERSION_UNSUPPORTED: 'SCHEMA_VERSION_UNSUPPORTED',
  INVALID_IDENTIFIER: 'INVALID_IDENTIFIER',
  VALIDATION_FAILED: 'VALIDATION_FAILED',
  STALE_REVISION: 'STALE_REVISION',
  DUPLICATE_EVENT: 'DUPLICATE_EVENT',
} as const;

export type ContractErrorCodeValue = (typeof ContractErrorCode)[keyof typeof ContractErrorCode];

export class ContractValidationError extends Error {
  readonly code: ContractErrorCodeValue;
  readonly details: Record<string, unknown>;
  readonly traceId?: string;

  constructor(options: {
    code: ContractErrorCodeValue;
    message: string;
    details?: Record<string, unknown>;
    traceId?: string;
  }) {
    super(options.message);
    this.name = 'ContractValidationError';
    this.code = options.code;
    this.details = options.details ?? {};
    this.traceId = options.traceId;
  }
}

export const apiErrorEnvelopeSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    code: z.string().min(1),
    message: z.string().min(1),
    details: z.record(z.unknown()).default({}),
    traceId: z.string().optional(),
  })
  .strict();

export type ApiErrorEnvelopeV1 = z.infer<typeof apiErrorEnvelopeSchema>;

export function toApiErrorEnvelope(error: ContractValidationError): ApiErrorEnvelopeV1 {
  return {
    schemaVersion: 1,
    code: error.code,
    message: error.message,
    details: error.details,
    traceId: error.traceId,
  };
}

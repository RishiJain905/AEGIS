import { z } from 'zod';

import {
  CURSOR_PAGINATION_SCHEMA_VERSION,
  IDEMPOTENCY_SCHEMA_VERSION,
  PROTOCOL_VERSION_V1,
} from './versioning';

export const protocolVersionSchema = z
  .object({
    major: z.number().int().min(1),
    minor: z.number().int().min(0),
  })
  .strict();

export const PROTOCOL_VERSION = {
  major: PROTOCOL_VERSION_V1,
  minor: 0,
} as const;

export const cursorPaginationSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    cursor: z.string().nullable().optional(),
    limit: z.number().int().min(1).max(1000).default(100),
    hasMore: z.boolean(),
    nextCursor: z.string().nullable().optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== CURSOR_PAGINATION_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported cursor pagination schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export const idempotencyMetadataSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    idempotencyKey: z.string().min(1).max(256),
    requestHash: z.string().nullable().optional(),
    replayed: z.boolean().default(false),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== IDEMPOTENCY_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported idempotency schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export type CursorPaginationV1 = z.infer<typeof cursorPaginationSchema>;
export type IdempotencyMetadataV1 = z.infer<typeof idempotencyMetadataSchema>;

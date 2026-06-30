import { z } from 'zod';

import { utcTimestampSchema } from './primitives';
import {
  IDEMPOTENCY_RECORD_SCHEMA_VERSION,
  OBJECT_METADATA_REFERENCE_SCHEMA_VERSION,
} from './versioning';

export const idempotencyRecordSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    scope: z.string().min(1).max(128),
    idempotencyKey: z.string().min(1).max(256),
    requestHash: z.string().nullable().optional(),
    responseRef: z.string().min(1).max(512),
    createdAt: utcTimestampSchema,
    replayed: z.boolean().default(false),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== IDEMPOTENCY_RECORD_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported idempotency record schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export const objectMetadataReferenceSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    objectKey: z.string().min(1).max(1024),
    checksum: z.string().min(1).max(128),
    contentType: z.string().min(1).max(256),
    sizeBytes: z.number().int().min(0),
    createdAt: utcTimestampSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== OBJECT_METADATA_REFERENCE_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported object metadata reference schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export type IdempotencyRecordV1 = z.infer<typeof idempotencyRecordSchema>;
export type ObjectMetadataReferenceV1 = z.infer<typeof objectMetadataReferenceSchema>;

import { z } from 'zod';

import { utcTimestampSchema } from './primitives';
import {
  PROVIDER_CREDENTIAL_STATUS_SCHEMA_VERSION,
  PROVIDER_MODEL_LIST_SCHEMA_VERSION,
} from './versioning';

// Cloud model-provider credentials and catalogue contracts. Mirrors
// packages/contracts-python/src/aegis_contracts/provider_credentials.py; keep the two
// in lockstep.
//
// Nothing here carries key material. The single plaintext fragment is `keyHint` — the
// last four characters — so an operator can tell which key is connected without the
// server disclosing it.

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

// Whether a user has a usable key for one provider — never the key itself.
export const providerCredentialStatusSchema = z
  .object({
    schemaVersion: schemaVersionCheck(PROVIDER_CREDENTIAL_STATUS_SCHEMA_VERSION),
    provider: z.string().min(1).max(64),
    configured: z.boolean(),
    keyHint: z.string().max(8).nullable().optional(),
    verifiedAt: utcTimestampSchema.nullable().optional(),
  })
  .strict();

export type ProviderCredentialStatusV1 = z.infer<typeof providerCredentialStatusSchema>;

// One selectable model. `label` is what the picker shows; `id` is what is sent.
export const providerModelEntrySchema = z
  .object({
    id: z.string().min(1).max(256),
    label: z.string().min(1).max(256),
  })
  .strict();

export type ProviderModelEntryV1 = z.infer<typeof providerModelEntrySchema>;

// A provider's live catalogue for the account that asked.
export const providerModelListSchema = z
  .object({
    schemaVersion: schemaVersionCheck(PROVIDER_MODEL_LIST_SCHEMA_VERSION),
    provider: z.string().min(1).max(64),
    models: z.array(providerModelEntrySchema).default([]),
  })
  .strict();

export type ProviderModelListV1 = z.infer<typeof providerModelListSchema>;

// One provider the launch dialog may offer. `requiresCredential` is what tells the
// dialog whether to demand a key before the run can launch; the local endpoint needs
// none. Fixture-serving providers (mock, recorded) are env-only and never listed.
export const loadoutProviderOptionSchema = z
  .object({
    id: z.string().min(1).max(64),
    label: z.string().min(1).max(128),
    requiresCredential: z.boolean(),
  })
  .strict();

export type LoadoutProviderOptionV1 = z.infer<typeof loadoutProviderOptionSchema>;

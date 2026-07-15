/** Phase 30 authentication and authorization contracts. */

import { z } from 'zod';

import { authoredIdSchema, runIdSchema, utcTimestampSchema } from './primitives';
import {
  AUTHENTICATED_ACTOR_SCHEMA_VERSION,
  AUTHORIZATION_DECISION_SCHEMA_VERSION,
  PERMISSION_SCHEMA_VERSION,
  RESOURCE_ACCESS_GRANT_SCHEMA_VERSION,
  ROLE_SCHEMA_VERSION,
  SECURITY_AUDIT_EVENT_SCHEMA_VERSION,
  SESSION_INFO_SCHEMA_VERSION,
} from './versioning';

const schemaVersionCheck = (expected: number) =>
  z
    .number()
    .int()
    .min(1)
    .refine((v) => v === expected);

export const platformRoleSchema = z.enum([
  'viewer',
  'analyst',
  'operator',
  'scenario_author',
  'admin',
]);

export const permissionSchema = z.enum([
  'runs:read',
  'runs:write',
  'investigation:read',
  'investigation:trigger',
  'approvals:decide',
  'replay:read',
  'replay:write',
  'reports:read',
  'reports:export',
  'reports:trigger',
  'scoring:read',
  'scoring:compute',
  'scoring:export',
  'scenarios:publish',
  'admin:manage',
  'ws:subscribe',
]);

export const authErrorCodeSchema = z.enum([
  'UNAUTHENTICATED',
  'FORBIDDEN',
  'SESSION_EXPIRED',
  'SESSION_REVOKED',
  'CSRF_FAILED',
  'INVALID_CREDENTIALS',
  'DEV_AUTH_DISABLED',
  'OIDC_FAILED',
]);

export const authorizationDecisionOutcomeSchema = z.enum(['allow', 'deny']);

export const securityAuditActionSchema = z.enum([
  'login',
  'logout',
  'denial',
  'role_change',
  'privileged_action',
]);

export const securityAuditOutcomeSchema = z.enum(['success', 'failure']);

export const authMethodSchema = z.enum(['oidc', 'dev']);

export const roleContractSchema = z
  .object({
    schemaVersion: schemaVersionCheck(ROLE_SCHEMA_VERSION),
    role: platformRoleSchema,
    permissions: z.array(permissionSchema).min(1),
  })
  .strict();

export const permissionContractSchema = z
  .object({
    schemaVersion: schemaVersionCheck(PERMISSION_SCHEMA_VERSION),
    permission: permissionSchema,
    description: z.string().min(1).max(512),
  })
  .strict();

export const authenticatedActorSchema = z
  .object({
    schemaVersion: schemaVersionCheck(AUTHENTICATED_ACTOR_SCHEMA_VERSION),
    userId: authoredIdSchema.refine((value) => value.startsWith('user:'), {
      message: 'Authenticated actor userId must use the user: namespace',
    }),
    displayName: z.string().min(1).max(256),
    roles: z.array(platformRoleSchema).min(1),
    permissions: z.array(permissionSchema).default([]),
    sessionId: z.string().min(8).max(128),
    authMethod: authMethodSchema,
  })
  .strict();

export const resourceAccessGrantSchema = z
  .object({
    schemaVersion: schemaVersionCheck(RESOURCE_ACCESS_GRANT_SCHEMA_VERSION),
    grantId: z.string().min(1).max(128),
    userId: authoredIdSchema,
    resourceType: z.literal('run'),
    resourceId: runIdSchema,
    permissions: z.array(permissionSchema).min(1),
    createdAt: utcTimestampSchema,
  })
  .strict();

export const authorizationDecisionSchema = z
  .object({
    schemaVersion: schemaVersionCheck(AUTHORIZATION_DECISION_SCHEMA_VERSION),
    outcome: authorizationDecisionOutcomeSchema,
    permission: permissionSchema,
    userId: authoredIdSchema,
    resourceType: z.string().max(64).nullable().optional(),
    resourceId: z.string().max(128).nullable().optional(),
    reasonCode: z.string().min(1).max(128),
    decidedAt: utcTimestampSchema,
  })
  .strict();

export const sessionInfoSchema = z
  .object({
    schemaVersion: schemaVersionCheck(SESSION_INFO_SCHEMA_VERSION),
    sessionId: z.string().min(8).max(128),
    userId: authoredIdSchema,
    authMethod: authMethodSchema,
    createdAt: utcTimestampSchema,
    expiresAt: utcTimestampSchema,
    revokedAt: utcTimestampSchema.nullable().optional(),
    csrfToken: z.string().min(16).max(128),
  })
  .strict();

const forbiddenDetailKeys = [
  'password',
  'token',
  'access_token',
  'refresh_token',
  'authorization',
  'cookie',
  'csrf',
  'secret',
];

export const securityAuditEventSchema = z
  .object({
    schemaVersion: schemaVersionCheck(SECURITY_AUDIT_EVENT_SCHEMA_VERSION),
    eventId: z.string().min(1).max(128),
    action: securityAuditActionSchema,
    outcome: securityAuditOutcomeSchema,
    actorUserId: authoredIdSchema.nullable().optional(),
    target: z.string().max(256).nullable().optional(),
    permission: permissionSchema.nullable().optional(),
    reasonCode: z.string().max(128).nullable().optional(),
    requestId: z.string().max(128).nullable().optional(),
    correlationId: z.string().max(128).nullable().optional(),
    occurredAt: utcTimestampSchema,
    details: z.record(z.string(), z.string()).default({}),
  })
  .strict()
  .superRefine((value, ctx) => {
    for (const key of Object.keys(value.details)) {
      const lowered = key.toLowerCase();
      if (forbiddenDetailKeys.some((part) => lowered.includes(part))) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'Security audit details must not contain secret field names',
          path: ['details', key],
        });
      }
    }
  });

export const devLoginRequestSchema = z
  .object({
    schemaVersion: schemaVersionCheck(1),
    userId: authoredIdSchema,
  })
  .strict();

export const authSessionResponseSchema = z
  .object({
    schemaVersion: schemaVersionCheck(1),
    authenticated: z.boolean(),
    actor: authenticatedActorSchema.nullable().optional(),
    session: sessionInfoSchema.nullable().optional(),
  })
  .strict();

export type PlatformRoleV1 = z.infer<typeof platformRoleSchema>;
export type PermissionV1 = z.infer<typeof permissionSchema>;
export type AuthenticatedActorV1 = z.infer<typeof authenticatedActorSchema>;
export type ResourceAccessGrantV1 = z.infer<typeof resourceAccessGrantSchema>;
export type AuthorizationDecisionV1 = z.infer<typeof authorizationDecisionSchema>;
export type SessionInfoV1 = z.infer<typeof sessionInfoSchema>;
export type SecurityAuditEventV1 = z.infer<typeof securityAuditEventSchema>;
export type DevLoginRequestV1 = z.infer<typeof devLoginRequestSchema>;
export type AuthSessionResponseV1 = z.infer<typeof authSessionResponseSchema>;

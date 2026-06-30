import { z } from 'zod';

export const WORKSPACE_VERSION = '0.0.0-phase00' as const;

export const aegisEnvironmentSchema = z.object({
  AEGIS_ENV: z.enum(['development', 'test', 'production']),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']),
  POSTGRES_HOST: z.string().min(1),
  POSTGRES_PORT: z.coerce.number().int().positive(),
  POSTGRES_DB: z.string().min(1),
  POSTGRES_USER: z.string().min(1),
  POSTGRES_PASSWORD: z.string().min(1),
  REDIS_URL: z.string().url(),
  S3_ENDPOINT: z.string().url(),
  S3_ACCESS_KEY: z.string().min(1),
  S3_SECRET_KEY: z.string().min(1),
  S3_BUCKET: z.string().min(1),
  API_PORT: z.coerce.number().int().positive(),
  WEB_PORT: z.coerce.number().int().positive(),
});

export type AegisEnvironment = z.infer<typeof aegisEnvironmentSchema>;

export function parseAegisEnvironment(env: Record<string, string | undefined>): AegisEnvironment {
  return aegisEnvironmentSchema.parse(env);
}

export function safeParseAegisEnvironment(env: Record<string, string | undefined>) {
  return aegisEnvironmentSchema.safeParse(env);
}

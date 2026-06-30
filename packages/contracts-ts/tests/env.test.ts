import { describe, expect, it } from 'vitest';
import { parseAegisEnvironment, safeParseAegisEnvironment } from '../src/index';

const validEnv = {
  AEGIS_ENV: 'development',
  LOG_LEVEL: 'info',
  POSTGRES_HOST: 'localhost',
  POSTGRES_PORT: '5432',
  POSTGRES_DB: 'aegis',
  POSTGRES_USER: 'aegis',
  POSTGRES_PASSWORD: 'aegis_dev',
  REDIS_URL: 'redis://localhost:6379/0',
  S3_ENDPOINT: 'http://localhost:9000',
  S3_ACCESS_KEY: 'aegis',
  S3_SECRET_KEY: 'aegis_dev_secret',
  S3_BUCKET: 'aegis-artifacts',
  API_PORT: '8000',
  WEB_PORT: '3000',
};

describe('aegisEnvironmentSchema', () => {
  it('accepts a valid environment', () => {
    const parsed = parseAegisEnvironment(validEnv);
    expect(parsed.AEGIS_ENV).toBe('development');
    expect(parsed.POSTGRES_PORT).toBe(5432);
  });

  it('rejects missing required variables', () => {
    const result = safeParseAegisEnvironment({ AEGIS_ENV: 'development' });
    expect(result.success).toBe(false);
  });

  it('rejects invalid enum values', () => {
    const result = safeParseAegisEnvironment({
      ...validEnv,
      AEGIS_ENV: 'staging',
    });
    expect(result.success).toBe(false);
  });

  it('rejects invalid URLs', () => {
    const result = safeParseAegisEnvironment({
      ...validEnv,
      REDIS_URL: 'not-a-url',
    });
    expect(result.success).toBe(false);
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { getDataSource } from '@/lib/api/create-client';

const ORIGINAL_DATA_SOURCE = process.env.NEXT_PUBLIC_AEGIS_DATA_SOURCE;
const ORIGINAL_NODE_ENV = process.env.NODE_ENV;

function setEnv(key: string, value: string | undefined): void {
  if (value === undefined) {
    delete (process.env as Record<string, string | undefined>)[key];
  } else {
    (process.env as Record<string, string | undefined>)[key] = value;
  }
}

describe('getDataSource', () => {
  beforeEach(() => {
    setEnv('NODE_ENV', 'test');
  });

  afterEach(() => {
    setEnv('NEXT_PUBLIC_AEGIS_DATA_SOURCE', ORIGINAL_DATA_SOURCE);
    setEnv('NODE_ENV', ORIGINAL_NODE_ENV);
    vi.restoreAllMocks();
  });

  it('defaults to api when the env var is unset', () => {
    setEnv('NEXT_PUBLIC_AEGIS_DATA_SOURCE', undefined);
    expect(getDataSource()).toBe('api');
  });

  it('treats any non-fixture value as api', () => {
    setEnv('NEXT_PUBLIC_AEGIS_DATA_SOURCE', 'api');
    expect(getDataSource()).toBe('api');
    setEnv('NEXT_PUBLIC_AEGIS_DATA_SOURCE', 'bogus');
    expect(getDataSource()).toBe('api');
  });

  it('honors an explicit fixture opt-in outside production', () => {
    setEnv('NEXT_PUBLIC_AEGIS_DATA_SOURCE', 'fixture');
    expect(getDataSource()).toBe('fixture');
  });

  it('refuses fixture in production and logs an error', () => {
    setEnv('NEXT_PUBLIC_AEGIS_DATA_SOURCE', 'fixture');
    setEnv('NODE_ENV', 'production');
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    expect(getDataSource()).toBe('api');
    expect(errorSpy).toHaveBeenCalledOnce();
  });
});

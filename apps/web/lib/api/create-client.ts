import { createFixtureProvider } from '@/lib/api/fixture-client';
import { createProductionClient } from '@/lib/api/production-client';
import type { AegisApiClient } from '@/lib/api/types';

export type DataSource = 'fixture' | 'api';

export function getDataSource(): DataSource {
  const source = process.env.NEXT_PUBLIC_AEGIS_DATA_SOURCE ?? 'fixture';
  return source === 'api' ? 'api' : 'fixture';
}

export function createApiClient(profileId?: string): AegisApiClient {
  if (getDataSource() === 'api') {
    return createProductionClient();
  }
  return createFixtureProvider({ profileId });
}

import { createFixtureProvider } from '@/lib/api/fixture-client';
import { createProductionClient } from '@/lib/api/production-client';
import type { AegisApiClient } from '@/lib/api/types';

export type DataSource = 'fixture' | 'api';

/**
 * Resolve the active data source.
 *
 * The API-backed client is the default: only an explicit
 * `NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture` selects the fixture provider, and even
 * then fixtures are refused in production builds (they leak synthetic runs,
 * graphs, and reports into real accounts). Tests, Storybook, and demo capture
 * scripts opt into fixtures explicitly, so they are unaffected.
 */
export function getDataSource(): DataSource {
  const source = process.env.NEXT_PUBLIC_AEGIS_DATA_SOURCE;
  if (source !== 'fixture') {
    return 'api';
  }
  if (process.env.NODE_ENV === 'production') {
    // eslint-disable-next-line no-console -- surface a misconfigured production build loudly.
    console.error(
      'NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture is not permitted in production builds; ' +
        'falling back to the API client.',
    );
    return 'api';
  }
  return 'fixture';
}

export function createApiClient(profileId?: string): AegisApiClient {
  if (getDataSource() === 'api') {
    return createProductionClient();
  }
  return createFixtureProvider({ profileId });
}

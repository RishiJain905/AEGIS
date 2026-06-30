'use client';

import { useSearchParams } from 'next/navigation';
import { createContext, useContext, useMemo, type ReactNode } from 'react';

import { createApiClient, type AegisApiClient } from '@/lib/api';

const ApiClientContext = createContext<AegisApiClient | null>(null);

export function ApiClientProvider({ children }: { children: ReactNode }) {
  const searchParams = useSearchParams();
  const profileId = searchParams.get('profile') ?? 'default';

  const client = useMemo(() => createApiClient(profileId), [profileId]);

  return <ApiClientContext.Provider value={client}>{children}</ApiClientContext.Provider>;
}

export function useApiClient(): AegisApiClient {
  const client = useContext(ApiClientContext);
  if (!client) {
    throw new Error('useApiClient must be used within ApiClientProvider');
  }
  return client;
}

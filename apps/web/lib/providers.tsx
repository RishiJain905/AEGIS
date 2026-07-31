'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';

import { AuthProvider } from '@/features/auth';
import { ThemeManager } from '@/features/shell/components/theme-manager';
import { queryRetryDelayMs, shouldRetryQuery } from '@/lib/api/retry-policy';

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        // Bounded attempts, jittered backoff, hard ceiling. See lib/api/retry-policy.
        retry: shouldRetryQuery,
        // TanStack hands the delay function `(attemptIndex, error)`; the policy's second
        // parameter is the jitter source, so it is called positionally here.
        retryDelay: (attemptIndex) => queryRetryDelayMs(attemptIndex),
        refetchOnWindowFocus: false,
      },
    },
  });
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeManager />
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}

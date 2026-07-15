import { Suspense, type ReactNode } from 'react';

import { AuthGate } from '@/features/auth';
import { ApiClientProvider } from '@/lib/api/api-client-provider';

export default function ShellLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={null}>
      <AuthGate>
        <ApiClientProvider>{children}</ApiClientProvider>
      </AuthGate>
    </Suspense>
  );
}

import { Suspense, type ReactNode } from 'react';

import { ApiClientProvider } from '@/lib/api/api-client-provider';

export default function ShellLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={null}>
      <ApiClientProvider>{children}</ApiClientProvider>
    </Suspense>
  );
}

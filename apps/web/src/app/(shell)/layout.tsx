import { Suspense, type ReactNode } from 'react';

import { AuthGate } from '@/features/auth';
import { TutorialController } from '@/features/tutorial';
import { ApiClientProvider } from '@/lib/api/api-client-provider';

export default function ShellLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={null}>
      <AuthGate>
        <ApiClientProvider>
          {children}
          {/* Shell-level guided walkthrough overlay. Inert unless the active run is the
              Synthetic Training Scenario; renders nothing otherwise. */}
          <TutorialController />
        </ApiClientProvider>
      </AuthGate>
    </Suspense>
  );
}

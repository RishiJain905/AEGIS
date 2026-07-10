'use client';

import { use } from 'react';

import { AfterActionDashboard } from '@/features/after-action/after-action-dashboard';
import { CommandCentreShell, ShellRouteGuard } from '@/features/shell/components';

interface AfterActionPageProps {
  params: Promise<{ runId: string }>;
}

export default function AfterActionPage({ params }: AfterActionPageProps) {
  const { runId } = use(params);

  return (
    <ShellRouteGuard runId={runId}>
      <CommandCentreShell>
        <div className="p-4 md:p-6">
          <AfterActionDashboard runId={runId} />
        </div>
      </CommandCentreShell>
    </ShellRouteGuard>
  );
}

'use client';

import { use } from 'react';

import { CommandCentreShell, ShellRouteGuard } from '@/features/shell/components';

interface RunPageProps {
  params: Promise<{ runId: string }>;
}

export default function RunPage({ params }: RunPageProps) {
  const { runId } = use(params);

  return (
    <ShellRouteGuard runId={runId}>
      <CommandCentreShell runId={runId} />
    </ShellRouteGuard>
  );
}

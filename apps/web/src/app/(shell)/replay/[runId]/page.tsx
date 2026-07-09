'use client';

import { use } from 'react';

import { ReplayCommandCentreShell } from '@/features/replay';
import { ShellRouteGuard } from '@/features/shell/components';

interface ReplayPageProps {
  params: Promise<{ runId: string }>;
}

export default function ReplayPage({ params }: ReplayPageProps) {
  const { runId } = use(params);

  return (
    <ShellRouteGuard runId={runId}>
      <ReplayCommandCentreShell runId={runId} />
    </ShellRouteGuard>
  );
}

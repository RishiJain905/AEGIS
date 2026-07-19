'use client';

import { use } from 'react';

import { ReplayCommandCentreShell } from '@/features/replay';
import { parseReplaySequenceParam } from '@/features/replay/lib/deep-link';
import { ShellRouteGuard } from '@/features/shell/components';

interface ReplayPageProps {
  params: Promise<{ runId: string }>;
  searchParams: Promise<{ sequence?: string | string[] }>;
}

export default function ReplayPage({ params, searchParams }: ReplayPageProps) {
  const { runId } = use(params);
  const { sequence } = use(searchParams);
  const initialSequence = parseReplaySequenceParam(sequence);

  return (
    <ShellRouteGuard runId={runId}>
      <ReplayCommandCentreShell runId={runId} initialSequence={initialSequence} />
    </ShellRouteGuard>
  );
}

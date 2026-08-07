'use client';

import { useSearchParams } from 'next/navigation';
import { use } from 'react';

import { CommandCentreShell, ShellRouteGuard } from '@/features/shell/components';

interface RunPageProps {
  params: Promise<{ runId: string }>;
}

export default function RunPage({ params }: RunPageProps) {
  const { runId } = use(params);
  // A restart relaunches the same scenario+seed, which derives the *same* run id — the
  // route alone would not remount the cockpit, and the live provider would keep narrating
  // the finished run. The restart control navigates with an epoch query param; keying the
  // shell on it forces a fresh bootstrap of the rebuilt run.
  const searchParams = useSearchParams();
  const restartEpoch = searchParams.get('restart') ?? '';

  return (
    <ShellRouteGuard runId={runId}>
      <CommandCentreShell key={restartEpoch} runId={runId} />
    </ShellRouteGuard>
  );
}

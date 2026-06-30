'use client';

import { use } from 'react';

import { EmptyState, Panel } from '@aegis/ui';

import { CommandCentreShell, ShellRouteGuard } from '@/features/shell/components';

interface ReplayPageProps {
  params: Promise<{ runId: string }>;
}

export default function ReplayPage({ params }: ReplayPageProps) {
  const { runId } = use(params);

  return (
    <ShellRouteGuard runId={runId}>
      <CommandCentreShell runId={runId}>
        <Panel title="Replay workspace" description="Historical playback — Phase 26">
          <EmptyState
            title="Replay engine not connected"
            description="Snapshot and replay controls arrive in later phases. Timeline cursor remains fixture-backed."
          />
        </Panel>
      </CommandCentreShell>
    </ShellRouteGuard>
  );
}

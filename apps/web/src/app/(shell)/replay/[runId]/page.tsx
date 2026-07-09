"use client";

import { use } from "react";

import { EmptyState, Panel } from "@aegis/ui";

import {
  CommandCentreShell,
  ShellRouteGuard,
} from "@/features/shell/components";

interface ReplayPageProps {
  params: Promise<{ runId: string }>;
}

export default function ReplayPage({ params }: ReplayPageProps) {
  const { runId } = use(params);

  return (
    <ShellRouteGuard runId={runId}>
      <CommandCentreShell runId={runId}>
        <Panel
          title="Replay workspace"
          description="Historical playback — Phase 26"
        >
          <EmptyState
            title="Replay UI not connected"
            description="Phase 25 backend snapshot/replay APIs exist under /api/v1/replay. Scrubbing controls and timeline UI arrive in Phase 26. Timeline cursor remains fixture-backed."
          />
        </Panel>
      </CommandCentreShell>
    </ShellRouteGuard>
  );
}

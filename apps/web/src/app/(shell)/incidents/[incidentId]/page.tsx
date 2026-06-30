'use client';

import { use } from 'react';

import { CommandCentreShell, ShellRouteGuard } from '@/features/shell/components';
import { useIncident } from '@/features/shell/hooks/use-shell-queries';

interface IncidentPageProps {
  params: Promise<{ incidentId: string }>;
}

function IncidentShell({ incidentId }: { incidentId: string }) {
  const incidentQuery = useIncident(incidentId);
  const runId = incidentQuery.data?.runId;

  return (
    <CommandCentreShell incidentId={incidentId} runId={runId}>
      {!runId && incidentQuery.isSuccess ? null : null}
    </CommandCentreShell>
  );
}

export default function IncidentPage({ params }: IncidentPageProps) {
  const { incidentId: rawIncidentId } = use(params);
  const incidentId = decodeURIComponent(rawIncidentId);

  return (
    <ShellRouteGuard incidentId={incidentId}>
      <IncidentShell incidentId={incidentId} />
    </ShellRouteGuard>
  );
}

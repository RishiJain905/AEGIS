'use client';

import { use } from 'react';

import { IncidentDetail } from '@/features/incidents';

// Incident-centric detail route (triage/case-management, not the live-run graph).
interface IncidentPageProps {
  params: Promise<{ incidentId: string }>;
}

export default function IncidentPage({ params }: IncidentPageProps) {
  const { incidentId: rawIncidentId } = use(params);
  const incidentId = decodeURIComponent(rawIncidentId);

  return <IncidentDetail incidentId={incidentId} />;
}

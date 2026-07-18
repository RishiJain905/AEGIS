'use client';

import { IncidentQueue } from '@/features/incidents';

// Incident-centric queue route (distinct from the live-run graph workspace).
export default function IncidentsPage() {
  return <IncidentQueue />;
}

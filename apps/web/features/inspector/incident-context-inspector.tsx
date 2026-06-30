'use client';

import type { AlertV1, IncidentV1 } from '@aegis/contracts-ts';
import { Badge, Panel } from '@aegis/ui';

export interface IncidentContextInspectorProps {
  incidents: IncidentV1[];
  alerts: AlertV1[];
  selectedEntityId: string | null;
}

export function IncidentContextInspector({
  incidents,
  alerts,
  selectedEntityId,
}: IncidentContextInspectorProps) {
  if (!selectedEntityId) {
    return null;
  }

  const relatedAlerts = alerts.filter((a) => a.assetId === selectedEntityId);
  const relatedIncidents = incidents.filter((inc) =>
    inc.alertIds.some((alertId) => relatedAlerts.some((a) => a.id === alertId)),
  );

  if (relatedAlerts.length === 0 && relatedIncidents.length === 0) {
    return null;
  }

  return (
    <Panel title="Incident context" density="compact" data-testid="incident-context-inspector">
      {relatedIncidents.map((incident) => (
        <div key={incident.id} className="mb-2">
          <p className="text-sm font-medium">{incident.title}</p>
          <Badge className="mt-1">{incident.state}</Badge>
        </div>
      ))}
      {relatedAlerts.length > 0 ? (
        <ul className="mt-2 flex flex-col gap-1">
          {relatedAlerts.map((alert) => (
            <li key={alert.id} className="text-xs">
              <span className="font-medium">{alert.title}</span>
              <span className="ml-2 text-[var(--aegis-text-muted)]">{alert.severity}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </Panel>
  );
}

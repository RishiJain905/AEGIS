'use client';

import type { AlertV1, IncidentV1 } from '@aegis/contracts-ts';
import { Badge, Panel } from '@aegis/ui';

import { InspectorLabel } from './inspector-primitives';

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
      <div className="flex flex-col gap-4">
        {relatedIncidents.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {relatedIncidents.map((incident) => (
              <li
                key={incident.id}
                className="flex flex-col gap-2 rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)] px-3 py-2"
              >
                <p className="text-sm font-medium leading-5 text-[var(--aegis-text-primary)]">
                  {incident.title}
                </p>
                <Badge className="self-start">{incident.state}</Badge>
              </li>
            ))}
          </ul>
        ) : null}

        {relatedAlerts.length > 0 ? (
          <div className="flex flex-col gap-2">
            <InspectorLabel>Related alerts</InspectorLabel>
            <ul className="flex flex-col gap-2">
              {relatedAlerts.map((alert) => (
                <li
                  key={alert.id}
                  className="flex items-start justify-between gap-2 rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)] px-3 py-2"
                >
                  <span className="min-w-0 flex-1 text-xs font-medium leading-5 text-[var(--aegis-text-primary)]">
                    {alert.title}
                  </span>
                  <Badge variant="outline" className="shrink-0">
                    {alert.severity}
                  </Badge>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

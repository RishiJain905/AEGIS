'use client';

import type { AlertV1, EvidenceAttachmentV1 } from '@aegis/contracts-ts';
import { EmptyState, Panel } from '@aegis/ui';

import { normalizeSeverity } from '../lib/incident-model';
import { SeverityChip } from './incident-primitives';

export function IncidentAlertsEvidence({
  alerts,
  evidence,
}: {
  alerts: readonly AlertV1[];
  evidence: readonly EvidenceAttachmentV1[];
}) {
  return (
    <Panel
      title="Linked alerts & evidence"
      description="Detections that opened this incident and evidence collected during investigation, with provenance."
      data-testid="incident-alerts-evidence"
    >
      <div className="flex flex-col gap-5">
        <section>
          <h3 className="mb-2 text-[0.6875rem] font-semibold uppercase tracking-[0.09em] text-[var(--aegis-text-muted)]">
            Alerts ({alerts.length})
          </h3>
          {alerts.length === 0 ? (
            <EmptyState
              title="No linked alerts"
              description="No alerts are linked to this incident."
            />
          ) : (
            <ul className="flex flex-col gap-2" role="list">
              {alerts.map((alert) => (
                <li
                  key={alert.id}
                  className="rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-raised)] p-3"
                  data-testid={`alert-${alert.id}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-medium text-[var(--aegis-text-primary)]">
                      {alert.title}
                    </span>
                    <SeverityChip severity={normalizeSeverity(alert.severity)} />
                  </div>
                  <p className="mt-1 font-mono text-[0.625rem] text-[var(--aegis-text-muted)]">
                    {alert.assetId}
                    {alert.detectorId ? ` · ${alert.detectorId}` : ''}
                    {typeof alert.confidence === 'number'
                      ? ` · confidence ${alert.confidence.toFixed(2)}`
                      : ''}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h3 className="mb-2 text-[0.6875rem] font-semibold uppercase tracking-[0.09em] text-[var(--aegis-text-muted)]">
            Evidence ({evidence.length})
          </h3>
          {evidence.length === 0 ? (
            <EmptyState
              title="No evidence yet"
              description="Investigation has not attached evidence to this incident."
            />
          ) : (
            <ul className="flex flex-col gap-2" role="list">
              {evidence.map((item) => (
                <li
                  key={item.id}
                  className="rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-raised)] p-3"
                  data-testid={`evidence-${item.id}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm text-[var(--aegis-text-primary)]">
                      {item.provenance.summary}
                    </span>
                    {item.isContradiction ? (
                      <span className="font-mono text-[0.625rem] uppercase tracking-[0.08em] text-[var(--aegis-status-suspicious)]">
                        Contradiction
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 font-mono text-[0.625rem] text-[var(--aegis-text-muted)]">
                    {item.provenance.sourceType} · {item.provenance.sourceId}
                    {item.provenance.collectedByTool
                      ? ` · via ${item.provenance.collectedByTool}`
                      : ''}
                    {` · confidence ${item.confidence.toFixed(2)}`}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </Panel>
  );
}

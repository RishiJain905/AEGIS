'use client';

import { Badge, Button, EmptyState, ErrorState, LoadingState, Panel } from '@aegis/ui';

import {
  GraphEntityInspector,
  InspectorLabel,
  InspectorMetric,
  InspectorMetricGrid,
  InspectorMonoValue,
} from '@/features/inspector';
import { useReplayStore } from '@/stores/replay-store';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

export function ReplayInspectorPanel() {
  const collapsed = useWorkspaceUiStore(
    (state) => state.panelPreferences.regions.inspector?.collapsed ?? false,
  );
  const togglePanelCollapsed = useWorkspaceUiStore((state) => state.togglePanelCollapsed);
  const selectedEntityId = useWorkspaceUiStore((state) => state.workspace.selectedEntityId);
  const setSelectedEntityId = useWorkspaceUiStore((state) => state.setSelectedEntityId);
  const loadStatus = useReplayStore((state) => state.loadStatus);
  const errorMessage = useReplayStore((state) => state.errorMessage);
  const state = useReplayStore((state) => state.reconstructedState);
  const cursor = useReplayStore((state) => state.cursor);

  if (collapsed) {
    return (
      <div className="flex w-12 shrink-0 flex-col items-center border-l border-[var(--aegis-border-default)] p-2">
        <Button
          variant="ghost"
          size="sm"
          data-testid="expand-inspector"
          onClick={() => {
            togglePanelCollapsed('inspector');
          }}
          aria-label="Expand inspector"
        >
          ‹
        </Button>
      </div>
    );
  }

  const snapshot = state?.graph ?? null;
  // The replay projection reconstructs one risk total per asset and nothing about how it
  // was reached — `ReplayRiskScoreV1` is `{ assetId, score, revision }`. The inspector
  // below therefore gets the total alone (`riskTotal`) rather than a padded-out
  // `AssetRiskScoreV1`: the padded shape rendered "Direct <score> / Propagated 0.00" in
  // the same metric grid the live inspector uses for a genuine breakdown, so an asset
  // whose risk propagated in from a compromised neighbour read as entirely its own.
  const selectedRisk =
    state?.riskScores.find(
      (score: NonNullable<typeof state>['riskScores'][number]) =>
        score.assetId === selectedEntityId,
    ) ?? null;

  return (
    <aside
      className="flex w-full shrink-0 flex-col border-l border-[var(--aegis-border-default)] bg-[var(--aegis-surface-panel)] lg:w-80 xl:w-96"
      data-testid="inspector-panel"
      aria-label="Historical inspector"
    >
      <div className="flex items-center justify-between border-b border-[var(--aegis-border-subtle)] bg-[linear-gradient(180deg,var(--aegis-surface-raised),var(--aegis-surface-panel))] px-4 py-3">
        <div>
          <p className="font-mono text-[0.625rem] uppercase tracking-[0.15em] text-[var(--aegis-text-muted)]">
            Context channel
          </p>
          <h2 className="text-sm font-semibold tracking-[0.04em]">Historical inspector</h2>
        </div>
        <Button
          variant="ghost"
          size="sm"
          data-testid="collapse-inspector"
          onClick={() => {
            togglePanelCollapsed('inspector');
          }}
          aria-label="Collapse inspector"
        >
          ›
        </Button>
      </div>

      <div className="flex-1 overflow-auto p-4">
        {loadStatus === 'loading' ? (
          <LoadingState message="Reconstructing inspector state…" />
        ) : null}
        {loadStatus === 'error' || loadStatus === 'unavailable' ? (
          <ErrorState message={errorMessage ?? 'Historical state unavailable.'} />
        ) : null}

        {loadStatus === 'ready' && state ? (
          <div className="flex flex-col gap-4">
            <Panel title="Replay cursor" density="compact" data-testid="replay-inspector-cursor">
              <div className="flex flex-col gap-3">
                <InspectorMetricGrid>
                  <InspectorMetric
                    label="Sequence"
                    value={cursor?.sequence ?? state.cursor.sequence}
                    span
                  />
                </InspectorMetricGrid>
                <div className="flex flex-col gap-1">
                  <InspectorLabel>State digest</InspectorLabel>
                  <InspectorMonoValue value={state.stateDigest} />
                </div>
              </div>
            </Panel>

            {snapshot ? (
              <GraphEntityInspector
                snapshot={snapshot}
                selectedEntityId={selectedEntityId}
                riskTotal={selectedRisk?.score ?? null}
              />
            ) : (
              <EmptyState
                title="No graph at this cursor"
                description="Scrub forward to reconstruct graph state."
              />
            )}

            <Panel title="Incidents" density="compact" data-testid="replay-inspector-incidents">
              {state.incidents.length === 0 ? (
                <p className="text-sm text-[var(--aegis-text-secondary)]">No incidents yet.</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {state.incidents.map((incident: (typeof state.incidents)[number]) => (
                    <li key={incident.id}>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="w-full justify-start"
                        data-testid={`replay-incident-${incident.id}`}
                        onClick={() => {
                          setSelectedEntityId(null);
                        }}
                      >
                        {incident.title}
                        <Badge className="ml-auto">{incident.state}</Badge>
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Evidence" density="compact" data-testid="replay-inspector-evidence">
              {state.evidence.length === 0 ? (
                <p className="text-sm text-[var(--aegis-text-secondary)]">No evidence yet.</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {state.evidence.map((item: (typeof state.evidence)[number]) => (
                    <li
                      key={item.id}
                      className="break-words rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)] px-3 py-2 text-xs leading-5 text-[var(--aegis-text-secondary)]"
                      data-testid={`replay-evidence-${item.id}`}
                    >
                      {item.summary}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel
              title="Proposals / approvals"
              density="compact"
              data-testid="replay-inspector-proposals"
            >
              {state.proposals.length === 0 ? (
                <p className="text-sm text-[var(--aegis-text-secondary)]">No proposals yet.</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {state.proposals.map((proposal: (typeof state.proposals)[number]) => (
                    <li
                      key={proposal.id}
                      className="break-words rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)] px-3 py-2 text-xs leading-5 text-[var(--aegis-text-secondary)]"
                      data-testid={`replay-proposal-${proposal.id}`}
                    >
                      <span className="font-mono text-[var(--aegis-text-primary)]">
                        {proposal.command}
                      </span>{' '}
                      · {proposal.status}
                      {state.approvals.some(
                        (approval: (typeof state.approvals)[number]) =>
                          approval.proposalId === proposal.id,
                      )
                        ? ' · approved historically'
                        : ''}
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-2 text-xs text-[var(--aegis-text-secondary)]">
                Approval mutations are disabled in historical mode.
              </p>
            </Panel>

            <Panel title="Reports" density="compact" data-testid="replay-inspector-reports">
              {state.reports.length === 0 ? (
                <p className="text-sm text-[var(--aegis-text-secondary)]">No reports yet.</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {state.reports.map((report: (typeof state.reports)[number]) => (
                    <li
                      key={report.reportId}
                      className="break-words rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)] px-3 py-2 text-xs leading-5 text-[var(--aegis-text-secondary)]"
                      data-testid={`replay-report-${report.reportId}`}
                    >
                      <span className="font-mono text-[var(--aegis-text-primary)]">
                        {report.reportId}
                      </span>{' '}
                      · {report.status}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        ) : null}
      </div>
    </aside>
  );
}

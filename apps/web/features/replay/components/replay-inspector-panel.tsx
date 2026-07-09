'use client';

import { Badge, Button, EmptyState, ErrorState, LoadingState, Panel } from '@aegis/ui';

import { GraphEntityInspector } from '@/features/inspector';
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
      <div className="flex items-center justify-between border-b border-[var(--aegis-border-subtle)] px-4 py-2">
        <h2 className="text-sm font-semibold">Historical inspector</h2>
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
              <p className="text-sm">Sequence {cursor?.sequence ?? state.cursor.sequence}</p>
              <p className="text-xs text-[var(--aegis-text-secondary)]">
                Digest {state.stateDigest.slice(0, 24)}…
              </p>
            </Panel>

            {snapshot ? (
              <GraphEntityInspector
                snapshot={snapshot}
                selectedEntityId={selectedEntityId}
                riskScore={
                  selectedRisk
                    ? {
                        schemaVersion: 1,
                        runId: state.runId,
                        assetId: selectedRisk.assetId,
                        total: selectedRisk.score,
                        direct: selectedRisk.score,
                        propagated: 0,
                        algorithmVersion: 'replay-projection-v1',
                        computedAtSequence: state.cursor.sequence,
                        simTime: state.cursor.simTime ?? state.provenance.reconstructedAt,
                        topContributions: [],
                      }
                    : null
                }
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
                <ul className="flex flex-col gap-2 text-sm">
                  {state.evidence.map((item: (typeof state.evidence)[number]) => (
                    <li key={item.id} data-testid={`replay-evidence-${item.id}`}>
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
                <ul className="flex flex-col gap-2 text-sm">
                  {state.proposals.map((proposal: (typeof state.proposals)[number]) => (
                    <li key={proposal.id} data-testid={`replay-proposal-${proposal.id}`}>
                      {proposal.command} · {proposal.status}
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
                <ul className="flex flex-col gap-2 text-sm">
                  {state.reports.map((report: (typeof state.reports)[number]) => (
                    <li key={report.reportId} data-testid={`replay-report-${report.reportId}`}>
                      {report.reportId} · {report.status}
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

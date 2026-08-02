'use client';

import { useEffect, useState } from 'react';

import { Button } from '@aegis/ui';

import { AgentChatPanel } from '@/features/agent-chat';
import { LiveRunControls, useLiveRun } from '@/features/live-run';
import { EventSearch, HypothesisLedger } from '@/features/operator-console';
import { AssetCommandBar } from '@/features/operator-actions';
import { OpsFeedPanel } from '@/features/ops-feed';
import { AlertsTab } from '@/features/shell/components/alerts-tab';
import { InspectorPanel } from '@/features/shell/components/inspector-panel';
import { VisualizationSlot } from '@/features/shell/components/visualization-slot';
import { WorkspaceDock } from '@/features/shell/components/workspace-dock';
import { useRunAlerts } from '@/features/shell/hooks/use-shell-queries';
import { RunTape } from '@/features/timeline';
import { isRunTerminal } from '@/lib/run-status';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

export interface RunWorkspaceProps {
  runId: string;
  incidentId?: string;
}

/** Collapse the rail and both docks together, or restore them all. */
function FocusStageButton() {
  const regions = useWorkspaceUiStore((state) => state.panelPreferences.regions);
  const setPanelCollapsed = useWorkspaceUiStore((state) => state.setPanelCollapsed);

  const focused =
    (regions.operationsRail?.collapsed ?? false) &&
    (regions.leftDock?.collapsed ?? false) &&
    (regions.rightDock?.collapsed ?? false);

  return (
    <Button
      variant={focused ? 'default' : 'outline'}
      size="sm"
      className="text-xs"
      data-testid="focus-stage"
      aria-pressed={focused}
      onClick={() => {
        setPanelCollapsed('operationsRail', !focused);
        setPanelCollapsed('leftDock', !focused);
        setPanelCollapsed('rightDock', !focused);
      }}
    >
      {focused ? 'Restore panels' : 'Focus graph'}
    </Button>
  );
}

/**
 * The execution-semantics ribbon over the command bar (BUG-012). Operator actions do not
 * queue behind a paused simulator — they execute against the frozen timeline — and once a
 * run ends they cannot execute at all. Both facts are said exactly where commands are
 * issued, in the same vocabulary as the SIM instrument above.
 */
function TimelineSemanticsNotice() {
  const liveRun = useLiveRun();
  if (liveRun === null || !liveRun.isLiveMode) {
    return null;
  }
  const runStatus = liveRun.state.runStatus;

  if (runStatus === 'paused') {
    return (
      <p
        role="status"
        data-testid="frozen-timeline-notice"
        className="flex flex-wrap items-baseline gap-x-2 rounded-[var(--aegis-radius-md)] border border-[color-mix(in_srgb,var(--aegis-status-suspicious)_40%,transparent)] bg-[color-mix(in_srgb,var(--aegis-status-suspicious)_8%,var(--aegis-surface-panel))] px-3 py-1.5 text-xs leading-5 text-[var(--aegis-text-secondary)]"
      >
        <span className="font-[family-name:var(--aegis-font-display)] text-[0.625rem] font-semibold uppercase tracking-[0.14em] text-[var(--aegis-status-suspicious)]">
          Sim paused
        </span>
        Commands still execute — against the frozen timeline, effective immediately.
      </p>
    );
  }

  if (isRunTerminal(runStatus)) {
    return (
      <p
        role="status"
        data-testid="run-ended-notice"
        className="flex flex-wrap items-baseline gap-x-2 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_70%,transparent)] px-3 py-1.5 text-xs leading-5 text-[var(--aegis-text-muted)]"
      >
        <span className="font-[family-name:var(--aegis-font-display)] text-[0.625rem] font-semibold uppercase tracking-[0.14em] text-[var(--aegis-text-secondary)]">
          Run ended
        </span>
        The timeline is read-only; commands can no longer execute.
      </p>
    );
  }

  return null;
}

/**
 * The active-run workspace, laid out in the cockpit's reading order.
 *
 * The status rail above answers "what is the situation"; this surface gives each of the
 * remaining questions a fixed home. The command deck holds transport, grouped by the fact
 * each control changes (SIM vs LINK). The graph is the play surface and keeps the middle
 * of the viewport at full height. The left dock is the operator's own channel (copilot,
 * evidence, hypotheses). The right dock is the situation channel in attention order —
 * Alerts first with a live count, then the Inspector for whatever is selected, then the
 * ops feed — and it follows the operator: selecting a node or opening a case flips it to
 * the Inspector. Underneath the graph sit the command bar for the selected asset and the
 * run tape; nothing is stacked below the fold.
 */
export function RunWorkspace({ runId, incidentId }: RunWorkspaceProps) {
  const alertsQuery = useRunAlerts(runId);
  const alertCount = alertsQuery.data?.length ?? 0;

  const selectedEntityId = useWorkspaceUiStore((state) => state.workspace.selectedEntityId);
  const selectedIncidentId = useWorkspaceUiStore((state) => state.workspace.selectedIncidentId);
  const activeIncidentId = incidentId ?? selectedIncidentId;

  const [rightTab, setRightTab] = useState('alerts');

  // The dock follows the operator's focus: naming a node (from the graph, an alert card,
  // or the feed) or opening a case is a statement of "show me this", so the Inspector
  // surfaces without a second click. Deliberate tab choices still stick — the effects only
  // fire when the selection itself changes.
  useEffect(() => {
    if (selectedEntityId !== null) {
      setRightTab('inspector');
    }
  }, [selectedEntityId]);
  useEffect(() => {
    if (activeIncidentId) {
      setRightTab('inspector');
    }
  }, [activeIncidentId]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div
        className="flex w-full flex-wrap items-center gap-x-3 gap-y-2"
        data-testid="command-deck"
      >
        <LiveRunControls />
        <div className="ml-auto flex items-center gap-2">
          <FocusStageButton />
        </div>
      </div>

      {/* `w-full` is deliberate on both rows: the deck and the dock row must always share
          the same right edge, whatever an ancestor's alignment does. */}
      <div className="flex min-h-0 w-full flex-1 flex-col gap-3 xl:flex-row">
        <WorkspaceDock
          region="leftDock"
          side="left"
          label="Operator console"
          data-testid="left-dock"
          tabs={[
            {
              id: 'copilot',
              label: 'Copilot',
              fill: true,
              content: <AgentChatPanel runId={runId} />,
            },
            {
              id: 'evidence',
              label: 'Evidence',
              content: <EventSearch runId={runId} />,
            },
            {
              id: 'hypotheses',
              label: 'Hypotheses',
              content: <HypothesisLedger runId={runId} />,
            },
          ]}
        />

        <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-2.5">
          <VisualizationSlot runId={runId} incidentId={incidentId} />
          <TimelineSemanticsNotice />
          <AssetCommandBar runId={runId} />
          <RunTape />
        </div>

        <WorkspaceDock
          region="rightDock"
          side="right"
          label="Situation channel"
          data-testid="right-dock"
          activeTab={rightTab}
          onActiveTabChange={setRightTab}
          tabs={[
            {
              id: 'alerts',
              label: 'Alerts',
              badge: alertCount,
              content: <AlertsTab runId={runId} />,
            },
            {
              id: 'inspector',
              label: 'Inspector',
              content: <InspectorPanel runId={runId} incidentId={incidentId} />,
            },
            {
              id: 'feed',
              label: 'Ops feed',
              fill: true,
              content: <OpsFeedPanel runId={runId} />,
            },
          ]}
        />
      </div>
    </div>
  );
}

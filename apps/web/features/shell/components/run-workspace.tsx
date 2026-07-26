'use client';

import { Button } from '@aegis/ui';

import { AgentChatPanel } from '@/features/agent-chat';
import { LiveRunControls } from '@/features/live-run';
import { EventSearch, HypothesisLedger } from '@/features/operator-console';
import { AssetCommandBar } from '@/features/operator-actions';
import { OpsFeedPanel } from '@/features/ops-feed';
import { InspectorPanel } from '@/features/shell/components/inspector-panel';
import { VisualizationSlot } from '@/features/shell/components/visualization-slot';
import { WorkspaceDock } from '@/features/shell/components/workspace-dock';
import { RunTape } from '@/features/timeline';
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
 * The active-run workspace.
 *
 * The graph is the play surface, so it takes the middle of the viewport at full height and
 * everything else flanks it in two collapsible docks: the operator channel on the left
 * (copilot, evidence search, hypotheses) and the context channel on the right (inspector,
 * ops feed). Underneath the graph sit the two things an operator needs without hunting —
 * the command bar for the selected asset, and the run tape. Nothing is stacked below the
 * fold, and nothing full-width steals height from the map.
 */
export function RunWorkspace({ runId, incidentId }: RunWorkspaceProps) {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <LiveRunControls />
        <div className="ml-auto flex items-center gap-2">
          <FocusStageButton />
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-3 xl:flex-row">
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
          <AssetCommandBar runId={runId} />
          <RunTape />
        </div>

        <WorkspaceDock
          region="rightDock"
          side="right"
          label="Context channel"
          data-testid="right-dock"
          tabs={[
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

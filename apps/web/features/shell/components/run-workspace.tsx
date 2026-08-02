'use client';

import { useEffect, useState } from 'react';

import { AgentChatPanel } from '@/features/agent-chat';
import { Console } from '@/features/console';
import { EventSearch, HypothesisLedger } from '@/features/operator-console';
import { OpsFeedPanel } from '@/features/ops-feed';
import { AlertsTab } from '@/features/shell/components/alerts-tab';
import { InspectorPanel } from '@/features/shell/components/inspector-panel';
import { VisualizationSlot } from '@/features/shell/components/visualization-slot';
import { WorkspaceDock } from '@/features/shell/components/workspace-dock';
import { useRunAlerts } from '@/features/shell/hooks/use-shell-queries';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

export interface RunWorkspaceProps {
  runId: string;
  incidentId?: string;
}

/**
 * The active-run workspace: one stage, no walls.
 *
 * The operational graph is the subject of the app, so it is the workspace — the stage
 * fills the viewport between the status rail and the Console, and everything else is
 * furniture on or around it. The Console is the operator's hands: one fused band across
 * the foot of the stage holding transport (SIM/LINK), the selected-asset command cluster
 * and the run tape. The docks flanking the stage are the last remnant of the old
 * three-column cockpit; they dissolve into the signals stack and context sheets over the
 * next phases of the rework.
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
        <div className="relative flex min-h-0 flex-1 flex-col" data-testid="cockpit-stage">
          <VisualizationSlot runId={runId} incidentId={incidentId} />
        </div>
        <Console runId={runId} />
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
  );
}

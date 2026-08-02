'use client';

import { useEffect } from 'react';

import { Chronicle, Console, CopilotSheet } from '@/features/console';
import { InspectorSheet } from '@/features/shell/components/inspector-sheet';
import { VisualizationSlot } from '@/features/shell/components/visualization-slot';
import { useCockpitShortcuts } from '@/features/shell/hooks/use-cockpit-shortcuts';
import { SignalsStack } from '@/features/signals';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';
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
 * furniture on or over it, each piece visibly about something. The Console is the
 * operator's hands (transport, selected-asset commands, tape, copilot chip). Signals —
 * the alerts surface — floats over the stage's top-right as ambient attention pressure.
 * Deep material arrives as context sheets tethered to their subject: the inspector on
 * the right, summoned by selection; the copilot on the left, summoned from the console.
 * And the run's history is the Chronicle: collapsed it is the console's tape, expanded
 * it is the full ops feed rising out of that same timeline. No walls remain.
 */
export function RunWorkspace({ runId, incidentId }: RunWorkspaceProps) {
  const selectedEntityId = useWorkspaceUiStore((state) => state.workspace.selectedEntityId);
  const selectedIncidentId = useWorkspaceUiStore((state) => state.workspace.selectedIncidentId);
  const activeIncidentId = incidentId ?? selectedIncidentId;

  const setInspectorSheetOpen = useCockpitUiStore((state) => state.setInspectorSheetOpen);

  useCockpitShortcuts();

  // Attention summons the inspector sheet: naming a node (from the graph, an alert card,
  // or the feed) or opening a case is a statement of "show me this". The effects fire on
  // selection *changes* only, so dismissing the sheet sticks until the operator names
  // something again (or presses I).
  useEffect(() => {
    if (selectedEntityId !== null) {
      setInspectorSheetOpen(true);
    }
  }, [selectedEntityId, setInspectorSheetOpen]);
  useEffect(() => {
    if (activeIncidentId) {
      setInspectorSheetOpen(true);
    }
  }, [activeIncidentId, setInspectorSheetOpen]);
  // ...and the sheet leaves when its subject deselects (a stage click, Escape).
  useEffect(() => {
    if (selectedEntityId === null && !activeIncidentId) {
      setInspectorSheetOpen(false);
    }
  }, [selectedEntityId, activeIncidentId, setInspectorSheetOpen]);

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-2.5">
      <div className="relative flex min-h-0 flex-1 flex-col" data-testid="cockpit-stage">
        <VisualizationSlot runId={runId} incidentId={incidentId} />
        <SignalsStack runId={runId} />
        <InspectorSheet runId={runId} incidentId={incidentId} />
        <CopilotSheet runId={runId} />
        <Chronicle runId={runId} />
      </div>
      <Console runId={runId} />
    </div>
  );
}

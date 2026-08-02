'use client';

import { ContextSheet } from '@aegis/ui';

import { InspectorPanel } from '@/features/shell/components/inspector-panel';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

export interface InspectorSheetProps {
  runId?: string;
  incidentId?: string;
}

/**
 * The inspector sheet — selection context sliding over the stage's right edge, tethered
 * to whatever the operator just named: a graph node, an alert's asset, an open case. It
 * auto-summons on selection (wired in the run workspace) and leaves when dismissed or
 * when its subject deselects.
 *
 * Width obeys the cockpit space budget: alone it takes at most min(30rem, 42%); when the
 * copilot sheet holds the other side both clamp to min(26rem, 32%), keeping ≥36% of the
 * stage un-occluded by construction.
 */
export function InspectorSheet({ runId, incidentId }: InspectorSheetProps) {
  const open = useCockpitUiStore((state) => state.inspectorSheetOpen);
  const setOpen = useCockpitUiStore((state) => state.setInspectorSheetOpen);
  const copilotOpen = useCockpitUiStore((state) => state.copilotSheetOpen);
  const selectedEntityId = useWorkspaceUiStore((state) => state.workspace.selectedEntityId);
  const shared = open && copilotOpen;

  return (
    <ContextSheet
      side="right"
      open={open}
      onClose={() => {
        setOpen(false);
      }}
      label="Inspector"
      subject={selectedEntityId}
      data-testid="inspector-sheet"
      data-budget={shared ? 'shared' : 'solo'}
      className={shared ? 'w-[min(26rem,32%)]' : 'w-[min(30rem,42%)]'}
    >
      <InspectorPanel runId={runId} incidentId={incidentId} />
    </ContextSheet>
  );
}

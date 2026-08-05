'use client';

import { ContextSheet } from '@aegis/ui';

import { useInspectorGraph } from '@/features/inspector';
import { InspectorPanel } from '@/features/shell/components/inspector-panel';
import { resolveCockpitFallbackFocus } from '@/lib/cockpit-focus';
import { inspectorSheetWidth } from '@/lib/cockpit-space';
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

  // The subject is a thing in the estate, not a row key: the operator reads the name they
  // see on the graph, with the id kept underneath for anyone who needs to quote it.
  const graph = useInspectorGraph(runId ?? '');
  const selectedNode = selectedEntityId
    ? (graph.snapshot?.nodes.find((node) => node.id === selectedEntityId) ?? null)
    : null;
  const subject = selectedNode?.label ?? selectedEntityId;
  const subjectDetail = selectedNode ? selectedEntityId : null;

  return (
    <ContextSheet
      side="right"
      open={open}
      onClose={() => {
        setOpen(false);
      }}
      label="Inspector"
      subject={subject}
      subjectDetail={subjectDetail}
      // Summoning the sheet folds the signals stack that may have held the invoker, so the
      // capsule (or the console) is where a keyboard operator lands when it closes.
      restoreFocusTo={resolveCockpitFallbackFocus}
      data-testid="inspector-sheet"
      data-budget={shared ? 'shared' : 'solo'}
      style={{ width: inspectorSheetWidth(shared) }}
    >
      <InspectorPanel runId={runId} incidentId={incidentId} />
    </ContextSheet>
  );
}

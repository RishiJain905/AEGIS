'use client';

import { useEffect } from 'react';

import { cn, typographyTokens } from '@aegis/ui';

import { AgentChatPanel } from '@/features/agent-chat';
import { Chronicle, Console, CopilotSheet } from '@/features/console';
import { EventSearch, HypothesisLedger } from '@/features/operator-console';
import { OpsFeedPanel } from '@/features/ops-feed';
import { AlertsTab } from '@/features/shell/components/alerts-tab';
import { InspectorPanel } from '@/features/shell/components/inspector-panel';
import { InspectorSheet } from '@/features/shell/components/inspector-sheet';
import { VisualizationSlot } from '@/features/shell/components/visualization-slot';
import { useCockpitShortcuts } from '@/features/shell/hooks/use-cockpit-shortcuts';
import { useStackedViewport } from '@/features/shell/hooks/use-stacked-viewport';
import { SignalsStack } from '@/features/signals';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

export interface RunWorkspaceProps {
  runId: string;
  incidentId?: string;
}

function StackedSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section aria-label={label} className="flex min-w-0 flex-col gap-3">
      <h2 className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-muted)]')}>{label}</h2>
      {children}
    </section>
  );
}

/**
 * Below xl the stage model degrades gracefully to stacked page flow: the graph on top,
 * the console as a sticky footer under it, and every summoned surface as a full-width
 * section in the cockpit's attention order — signals, inspector, copilot material,
 * chronicle. Same capabilities, no floating furniture, normal scrolling.
 */
function StackedRunWorkspace({ runId, incidentId }: RunWorkspaceProps) {
  return (
    <div className="flex w-full flex-col gap-5" data-testid="stacked-workspace">
      <div className="flex h-[60vh] min-h-[24rem] flex-col">
        <VisualizationSlot runId={runId} incidentId={incidentId} />
      </div>
      <div className="sticky bottom-2 z-30">
        <Console runId={runId} />
      </div>
      <StackedSection label="Signals">
        <AlertsTab runId={runId} />
      </StackedSection>
      <StackedSection label="Inspector">
        <InspectorPanel runId={runId} incidentId={incidentId} />
      </StackedSection>
      <StackedSection label="Copilot">
        <AgentChatPanel runId={runId} />
        <EventSearch runId={runId} />
        <HypothesisLedger runId={runId} />
      </StackedSection>
      <StackedSection label="Chronicle">
        <OpsFeedPanel runId={runId} />
      </StackedSection>
    </div>
  );
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
  const stacked = useStackedViewport();

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

  if (stacked) {
    return <StackedRunWorkspace runId={runId} incidentId={incidentId} />;
  }

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

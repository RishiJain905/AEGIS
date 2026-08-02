'use client';

import { ContextSheet, Tabs, TabsContent, TabsList, TabsTrigger } from '@aegis/ui';

import { AgentChatPanel } from '@/features/agent-chat';
import { EventSearch, HypothesisLedger } from '@/features/operator-console';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';

export interface CopilotSheetProps {
  runId: string;
}

/**
 * The copilot sheet — the colleague, summoned over the stage's left edge from the
 * console's presence chip or `C`. The agent chat is its face; Evidence and Hypotheses
 * ride along as its secondary tabs because they are operator-console material and belong
 * with the colleague, not in a parked column.
 *
 * Width obeys the cockpit space budget: alone it takes at most min(28rem, 40%); when the
 * inspector sheet holds the other side both clamp to min(26rem, 32%), keeping ≥36% of
 * the stage un-occluded by construction.
 */
export function CopilotSheet({ runId }: CopilotSheetProps) {
  const open = useCockpitUiStore((state) => state.copilotSheetOpen);
  const setOpen = useCockpitUiStore((state) => state.setCopilotSheetOpen);
  const inspectorOpen = useCockpitUiStore((state) => state.inspectorSheetOpen);
  const seed = useCockpitUiStore((state) => state.copilotSeed);
  const shared = open && inspectorOpen;

  return (
    <ContextSheet
      side="left"
      open={open}
      onClose={() => {
        setOpen(false);
      }}
      label="Copilot"
      fill
      data-testid="copilot-sheet"
      data-budget={shared ? 'shared' : 'solo'}
      className={shared ? 'w-[min(26rem,32%)]' : 'w-[min(28rem,40%)]'}
    >
      <Tabs defaultValue="copilot" className="flex min-h-0 flex-1 flex-col">
        <TabsList aria-label="Copilot views" className="mb-2">
          <TabsTrigger value="copilot" data-testid="copilot-sheet-tab-copilot">
            Copilot
          </TabsTrigger>
          <TabsTrigger value="evidence" data-testid="copilot-sheet-tab-evidence">
            Evidence
          </TabsTrigger>
          <TabsTrigger value="hypotheses" data-testid="copilot-sheet-tab-hypotheses">
            Hypotheses
          </TabsTrigger>
        </TabsList>
        <TabsContent value="copilot" className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <AgentChatPanel runId={runId} composerSeed={seed} />
        </TabsContent>
        <TabsContent value="evidence" className="min-h-0 flex-1 overflow-y-auto">
          <EventSearch runId={runId} />
        </TabsContent>
        <TabsContent value="hypotheses" className="min-h-0 flex-1 overflow-y-auto">
          <HypothesisLedger runId={runId} />
        </TabsContent>
      </Tabs>
    </ContextSheet>
  );
}

'use client';

import { Panel, Tabs, TabsContent, TabsList, TabsTrigger } from '@aegis/ui';

import { EventSearch } from './event-search';
import { HypothesisLedger } from './hypothesis-ledger';

export interface OperatorConsolePanelProps {
  runId: string;
}

/**
 * The operator console — the player's side of the 2v1. It exposes the same read surface the
 * agents work from: log/event search over the run's evidence pool, plus a pinned-hypothesis
 * ledger. The player investigates personally here, as a peer to the AI, not just a spectator.
 */
export function OperatorConsolePanel({ runId }: OperatorConsolePanelProps) {
  return (
    <Panel
      title="Operator console"
      description="Work the evidence the agents see — search the run and pin what you think is happening."
      density="compact"
      data-testid="operator-console-panel"
    >
      <Tabs defaultValue="search" className="flex flex-col gap-3">
        <TabsList aria-label="Operator console views">
          <TabsTrigger value="search">Event search</TabsTrigger>
          <TabsTrigger value="hypotheses">Hypotheses</TabsTrigger>
        </TabsList>
        <TabsContent value="search">
          <EventSearch runId={runId} />
        </TabsContent>
        <TabsContent value="hypotheses">
          <HypothesisLedger runId={runId} />
        </TabsContent>
      </Tabs>
    </Panel>
  );
}

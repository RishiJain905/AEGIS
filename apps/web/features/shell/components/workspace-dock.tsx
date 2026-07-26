'use client';

import { useEffect, useState, type ReactNode } from 'react';

import { Button, Tabs, TabsContent, TabsList, TabsTrigger, cn, typographyTokens } from '@aegis/ui';

import type { PanelRegion } from '@/features/shell/contracts/panel-preferences';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

export interface WorkspaceDockTab {
  id: string;
  /** Short tab label; also the vertical label on the collapsed strip. */
  label: string;
  content: ReactNode;
  /**
   * True when the content fills the dock and scrolls internally (a chat log, a feed);
   * false (default) lets the dock scroll a stack of panels.
   */
  fill?: boolean;
}

export interface WorkspaceDockProps {
  /** Persisted collapse region backing this dock. */
  region: Extract<PanelRegion, 'leftDock' | 'rightDock'>;
  /** Which edge of the stage the dock sits on (drives the collapse chevron). */
  side: 'left' | 'right';
  /** Eyebrow above the tabs, and the dock's accessible name. */
  label: string;
  tabs: WorkspaceDockTab[];
  'data-testid'?: string;
}

function ChevronIcon({ direction }: { direction: 'left' | 'right' }) {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <path d={direction === 'left' ? 'm12.5 4-6 6 6 6' : 'm7.5 4 6 6-6 6'} />
    </svg>
  );
}

/**
 * A collapsible, tabbed side dock for the run workspace. Docks flank the graph stage and
 * hold everything that is not the play surface, so the graph keeps the middle of the
 * viewport. Collapsed, a dock shrinks to a labelled strip: the tab names stay readable and
 * clicking one reopens the dock straight to that tab, so nothing gets lost when the
 * operator wants the map full-bleed.
 */
export function WorkspaceDock({
  region,
  side,
  label,
  tabs,
  'data-testid': testId,
}: WorkspaceDockProps) {
  const collapsed = useWorkspaceUiStore(
    (state) => state.panelPreferences.regions[region]?.collapsed ?? false,
  );
  const setPanelCollapsed = useWorkspaceUiStore((state) => state.setPanelCollapsed);

  const firstTabId = tabs[0]?.id ?? '';
  const [activeId, setActiveId] = useState(firstTabId);

  // Keep the active tab valid if the tab set changes (e.g. a run-scoped tab drops out).
  useEffect(() => {
    if (!tabs.some((tab) => tab.id === activeId)) {
      setActiveId(firstTabId);
    }
  }, [tabs, activeId, firstTabId]);

  if (collapsed) {
    return (
      <div
        className="flex w-11 shrink-0 flex-col items-center gap-2 rounded-[var(--aegis-radius-lg)] border border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_80%,transparent)] py-2 shadow-[var(--aegis-shadow-panel)] backdrop-blur-xl"
        data-testid={testId ? `${testId}-collapsed` : undefined}
      >
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          data-testid={`expand-${region}`}
          aria-label={`Expand ${label}`}
          onClick={() => {
            setPanelCollapsed(region, false);
          }}
        >
          <ChevronIcon direction={side === 'left' ? 'right' : 'left'} />
        </Button>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            data-testid={`dock-strip-${tab.id}`}
            onClick={() => {
              setActiveId(tab.id);
              setPanelCollapsed(region, false);
            }}
            className="rounded-[var(--aegis-radius-sm)] px-1 py-3 font-[family-name:var(--aegis-font-mono)] text-[10px] uppercase tracking-[0.16em] text-[var(--aegis-text-muted)] transition-colors hover:bg-[var(--aegis-surface-hover)] hover:text-[var(--aegis-text-primary)]"
            style={{ writingMode: 'vertical-rl' }}
          >
            {tab.label}
          </button>
        ))}
      </div>
    );
  }

  return (
    <aside
      aria-label={label}
      data-testid={testId}
      className={cn(
        'flex min-h-0 shrink-0 flex-col overflow-hidden rounded-[var(--aegis-radius-lg)] border border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_80%,transparent)] shadow-[var(--aegis-shadow-panel)] backdrop-blur-xl',
        side === 'left' ? 'w-[19rem] 2xl:w-[21rem]' : 'w-[20rem] 2xl:w-[22rem]',
      )}
    >
      <Tabs
        value={activeId}
        onValueChange={setActiveId}
        className="flex min-h-0 flex-1 flex-col overflow-hidden"
      >
        <div className="flex items-start gap-2 border-b border-[var(--aegis-border-subtle)] px-3 pb-2 pt-2.5">
          <div className="min-w-0 flex-1">
            <p className={cn(typographyTokens.eyebrow, 'mb-1.5 text-[var(--aegis-text-muted)]')}>
              {label}
            </p>
            <TabsList aria-label={`${label} views`} className="flex-wrap">
              {tabs.map((tab) => (
                <TabsTrigger key={tab.id} value={tab.id} data-testid={`dock-tab-${tab.id}`}>
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0"
            data-testid={`collapse-${region}`}
            aria-label={`Collapse ${label}`}
            onClick={() => {
              setPanelCollapsed(region, true);
            }}
          >
            <ChevronIcon direction={side === 'left' ? 'left' : 'right'} />
          </Button>
        </div>
        {tabs.map((tab) => (
          <TabsContent
            key={tab.id}
            value={tab.id}
            className={cn(
              'flex min-h-0 flex-1 flex-col p-3',
              tab.fill ? 'overflow-hidden' : 'overflow-y-auto',
            )}
          >
            {tab.content}
          </TabsContent>
        ))}
      </Tabs>
    </aside>
  );
}

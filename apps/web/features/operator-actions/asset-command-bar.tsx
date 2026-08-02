'use client';

import { useState } from 'react';

import {
  Badge,
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
  cn,
} from '@aegis/ui';

import { useLiveRun } from '@/features/live-run';
import { isRunTerminal } from '@/lib/run-status';

import { AssetDetailDrawer } from './asset-detail-drawer';
import { CommandMenuItems } from './command-menu-items';
import { useAssetActionRunner } from './use-asset-action-runner';
import { useAssetCommands } from './use-asset-commands';
import { useSelectedAsset } from './use-selected-asset';

/** How many commands get their own button before the rest fall back to the dropdown. */
const QUICK_ACTION_LIMIT = 3;

/** Why the controls are dead, on hover, for anyone who missed the ribbon above the bar. */
const RUN_ENDED_HINT = 'The run has ended — commands can no longer execute.';

export interface AssetCommandBarProps {
  runId: string;
}

/**
 * The operator's command line, docked under the graph for the whole engagement.
 *
 * Acting on an asset is the core verb of the game, so it gets a permanent band rather than
 * a section buried in the inspector: select a node and its commands are already on screen —
 * see a suspicious node, act on it, two interactions. The quick buttons are just the first
 * few entries of {@link useAssetCommands}, so an asset-type-specific catalogue reorders or
 * replaces them without touching this layout; everything else stays reachable in the
 * dropdown, and the same commands are one right-click away on the graph itself.
 */
export function AssetCommandBar({ runId }: AssetCommandBarProps) {
  const selected = useSelectedAsset(runId);
  const [drawerOpen, setDrawerOpen] = useState(false);

  if (!selected) {
    return (
      <div
        className="flex min-h-[3.25rem] shrink-0 items-center gap-3 rounded-[var(--aegis-radius-lg)] border border-dashed border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_60%,transparent)] px-4 py-2"
        data-testid="asset-command-bar"
        data-state="empty"
      >
        <span className="font-[family-name:var(--aegis-font-display)] text-[0.625rem] font-semibold uppercase tracking-[0.16em] text-[var(--aegis-text-muted)]">
          Operator command
        </span>
        <p className="text-xs text-[var(--aegis-text-secondary)]">
          Select an asset on the graph to command it — or right-click a node for the same actions
          where you found it.
        </p>
      </div>
    );
  }

  return (
    <SelectedAssetCommandBar
      key={selected.node.id}
      runId={runId}
      assetId={selected.node.id}
      assetLabel={selected.node.label}
      assetType={selected.node.assetType}
      status={selected.node.status}
      disclosed={selected.disclosed}
      onOpenDrawer={() => {
        setDrawerOpen(true);
      }}
    >
      <AssetDetailDrawer
        runId={runId}
        node={selected.node}
        disclosed={selected.disclosed}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
      />
    </SelectedAssetCommandBar>
  );
}

interface SelectedAssetCommandBarProps {
  runId: string;
  assetId: string;
  assetLabel: string;
  assetType: string;
  status: 'normal' | 'suspicious' | 'under_investigation' | 'contained' | 'compromised';
  disclosed: boolean;
  onOpenDrawer: () => void;
  children: React.ReactNode;
}

/**
 * Split out so the action runner (and its confirm dialog) is remounted per asset — a
 * pending confirmation must never survive the operator selecting a different node.
 */
function SelectedAssetCommandBar({
  runId,
  assetId,
  assetLabel,
  assetType,
  status,
  disclosed,
  onOpenDrawer,
  children,
}: SelectedAssetCommandBarProps) {
  const commands = useAssetCommands(assetType);
  const runner = useAssetActionRunner({ runId, assetId, assetLabel });
  const quickActions = commands.slice(0, QUICK_ACTION_LIMIT);

  // A finished run accepts no commands. The ribbon directly above says so, but saying it
  // while every button still invites a click is worse than not saying it at all — the
  // operator learns the sentence is decoration. Read-only affordances (Deep dive) stay live:
  // examining an asset after the fact is most of what an ended run is for.
  const liveRun = useLiveRun();
  const commandsDisabled = runner.isPending || isRunTerminal(liveRun?.state.runStatus);

  return (
    <div
      className="flex min-h-[3.25rem] shrink-0 flex-wrap items-center gap-x-3 gap-y-2 rounded-[var(--aegis-radius-lg)] border border-[var(--aegis-accent-line)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_86%,transparent)] px-4 py-2 shadow-[var(--aegis-shadow-control)] backdrop-blur-xl"
      data-testid="asset-command-bar"
      data-state="selected"
      aria-label={`Operator command · ${assetLabel}`}
    >
      <div className="flex min-w-0 items-center gap-2.5">
        <span
          aria-hidden="true"
          className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--aegis-accent-cyan)] shadow-[0_0_10px_var(--aegis-accent-cyan)]"
        />
        <span
          className="truncate text-sm font-semibold text-[var(--aegis-text-primary)]"
          data-testid="command-bar-asset-label"
        >
          {assetLabel}
        </span>
        <span className="shrink-0 font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
          {assetType}
        </span>
        {disclosed ? (
          <Badge nodeStatus={status}>{status.replace(/_/g, ' ')}</Badge>
        ) : (
          <Badge variant="outline">undisclosed</Badge>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 md:ml-auto">
        {quickActions.map((command) => (
          <Button
            key={command.command}
            variant="outline"
            size="sm"
            disabled={commandsDisabled}
            data-testid={`command-bar-action-${command.command}`}
            title={isRunTerminal(liveRun?.state.runStatus) ? RUN_ENDED_HINT : command.summary}
            onClick={() => {
              runner.select(command);
            }}
            className={cn(
              'text-xs',
              command.actionClass === 'class_3' && 'text-[var(--aegis-risk-high)]',
            )}
          >
            {command.label}
          </Button>
        ))}
        {commands.length > quickActions.length ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="secondary"
                size="sm"
                className="text-xs"
                disabled={commandsDisabled}
                title={isRunTerminal(liveRun?.state.runStatus) ? RUN_ENDED_HINT : undefined}
                data-testid="command-bar-all-actions"
              >
                <span>All actions</span>
                <span aria-hidden="true" className="ml-2 text-[var(--aegis-text-muted)]">
                  ▾
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-[15rem]">
              <CommandMenuItems commands={commands} onSelect={runner.select} />
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
        <Button
          variant="ghost"
          size="sm"
          className="text-xs"
          data-testid="open-asset-deep-dive"
          onClick={onOpenDrawer}
        >
          Deep dive
        </Button>
      </div>

      {runner.overlays}
      {children}
    </div>
  );
}

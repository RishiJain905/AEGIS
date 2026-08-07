'use client';

import { useEffect, useState } from 'react';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@aegis/ui';

import { useLiveRun } from '@/features/live-run';
import { isRunTerminal } from '@/lib/run-status';

import { CommandMenuItems } from './command-menu-items';
import { useAssetActionRunner } from './use-asset-action-runner';
import { useAssetCommands } from './use-asset-commands';

export interface AssetContextTarget {
  nodeId: string;
  label: string;
  /** The node's asset class, so the right-click menu offers the same verbs the bar does. */
  assetType: string | null;
  /** Pointer position in pixels, relative to the positioned graph frame. */
  x: number;
  y: number;
}

export interface AssetContextMenuProps {
  runId: string;
  /** The node the operator right-clicked, or null once the menu is dismissed. */
  target: AssetContextTarget | null;
  onDismiss: () => void;
}

/**
 * Right-click commands on a graph node. The operator acts where they found the problem:
 * spot a suspicious asset, right-click, execute — no trip to a side panel.
 *
 * The component outlives `target` going null on purpose: choosing a Class 2/3 command
 * closes the menu and opens the confirm dialog, which must survive the dismissal. It
 * remounts (dropping any pending confirmation) when a different node is targeted.
 */
export function AssetContextMenu({ runId, target, onDismiss }: AssetContextMenuProps) {
  const [anchor, setAnchor] = useState<AssetContextTarget | null>(target);

  useEffect(() => {
    if (target) {
      setAnchor(target);
    }
  }, [target]);

  if (!anchor) {
    return null;
  }

  return (
    <AssetContextMenuBody
      key={anchor.nodeId}
      runId={runId}
      anchor={anchor}
      open={target !== null}
      onDismiss={onDismiss}
    />
  );
}

function AssetContextMenuBody({
  runId,
  anchor,
  open,
  onDismiss,
}: {
  runId: string;
  anchor: AssetContextTarget;
  open: boolean;
  onDismiss: () => void;
}) {
  const commands = useAssetCommands(anchor.assetType);
  const runner = useAssetActionRunner({
    runId,
    assetId: anchor.nodeId,
    assetLabel: anchor.label,
  });
  // Same gating as the command bar: on an ended run the menu must not offer commands the
  // server will refuse. The menu has no room for a hint, so the items themselves go
  // disabled — a dead item reads as a dead item, not as a broken click.
  const runEnded = isRunTerminal(useLiveRun()?.state.runStatus);

  return (
    <>
      <DropdownMenu
        open={open}
        onOpenChange={(next) => {
          if (!next) {
            onDismiss();
          }
        }}
      >
        <DropdownMenuTrigger asChild>
          <span
            aria-hidden="true"
            data-testid="asset-context-menu-anchor"
            className="pointer-events-none absolute block h-px w-px"
            style={{ left: anchor.x, top: anchor.y }}
          />
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="start"
          className="min-w-[15rem]"
          data-testid="asset-context-menu"
        >
          <DropdownMenuLabel className="text-[var(--aegis-text-primary)]">
            {anchor.label}
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <CommandMenuItems commands={commands} onSelect={runner.select} disabled={runEnded} />
        </DropdownMenuContent>
      </DropdownMenu>

      {runner.overlays}
    </>
  );
}

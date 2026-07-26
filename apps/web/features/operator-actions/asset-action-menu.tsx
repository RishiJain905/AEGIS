'use client';

import { Button, DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from '@aegis/ui';

import { CommandMenuItems } from './command-menu-items';
import { useAssetActionRunner } from './use-asset-action-runner';
import { useAssetCommands } from './use-asset-commands';

export interface AssetActionMenuProps {
  runId: string;
  assetId: string;
  assetLabel: string;
  /** Optional incident anchor; the service resolves a run-scoped incident when omitted. */
  incidentId?: string | null;
  /** Render as a compact icon-ish trigger (graph selection) vs a full-width button (drawer). */
  variant?: 'compact' | 'block';
  /** Trigger copy; the stage command bar labels this "All actions". */
  label?: string;
  disabled?: boolean;
}

/**
 * The operator's dropdown of every command available on an asset. Execution, confirmation
 * gating and result reporting all live in {@link useAssetActionRunner}, which this shares
 * with the stage command bar and the graph context menu.
 */
export function AssetActionMenu({
  runId,
  assetId,
  assetLabel,
  incidentId,
  variant = 'block',
  label = 'Operator actions',
  disabled,
}: AssetActionMenuProps) {
  const commands = useAssetCommands(assetId);
  const runner = useAssetActionRunner({
    runId,
    assetId,
    assetLabel,
    incidentId,
  });

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant={variant === 'compact' ? 'outline' : 'secondary'}
            size="sm"
            disabled={disabled || runner.isPending}
            data-testid="asset-action-trigger"
            className={variant === 'block' ? 'w-full justify-between' : undefined}
          >
            <span>{label}</span>
            <span aria-hidden="true" className="ml-2 text-[var(--aegis-text-muted)]">
              ▾
            </span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="min-w-[15rem]">
          <CommandMenuItems commands={commands} onSelect={runner.select} />
        </DropdownMenuContent>
      </DropdownMenu>

      {runner.overlays}
    </>
  );
}

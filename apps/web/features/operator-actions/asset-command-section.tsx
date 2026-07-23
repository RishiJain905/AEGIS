'use client';

import { useState } from 'react';

import { Button, Panel } from '@aegis/ui';

import { AssetActionMenu } from './asset-action-menu';
import { AssetDetailDrawer } from './asset-detail-drawer';
import { useSelectedAsset } from './use-selected-asset';

/**
 * Inspector section that turns the selected graph asset into an operator command surface:
 * the direct-action menu inline, plus a deep-dive drawer. Renders nothing when no asset is
 * selected, so it slots quietly into the inspector alongside the read-only entity details.
 */
export function AssetCommandSection({ runId }: { runId: string }) {
  const selected = useSelectedAsset(runId);
  const [drawerOpen, setDrawerOpen] = useState(false);

  if (!selected) {
    return null;
  }

  return (
    <Panel title="Operator command" density="compact" data-testid="asset-command-section">
      <div className="flex flex-col gap-2">
        <p className="text-xs text-[var(--aegis-text-secondary)]">
          Act on{' '}
          <span className="font-medium text-[var(--aegis-text-primary)]">
            {selected.node.label}
          </span>{' '}
          directly, as incident commander.
        </p>
        <AssetActionMenu
          runId={runId}
          assetId={selected.node.id}
          assetLabel={selected.node.label}
        />
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setDrawerOpen(true);
          }}
          className="self-start"
          data-testid="open-asset-deep-dive"
        >
          Open deep-dive
        </Button>
      </div>
      <AssetDetailDrawer
        runId={runId}
        node={selected.node}
        disclosed={selected.disclosed}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
      />
    </Panel>
  );
}

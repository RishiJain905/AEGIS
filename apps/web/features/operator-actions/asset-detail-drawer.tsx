'use client';

import {
  Badge,
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
  cn,
} from '@aegis/ui';
import type { GraphNodeV1 } from '@aegis/contracts-ts';

import { AssetActionMenu } from './asset-action-menu';

function StatBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div className="flex items-center gap-2">
      <span className="w-20 font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
        {label}
      </span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--aegis-border-subtle)]">
        <div className="h-full bg-[var(--aegis-accent)]" style={{ width: `${String(pct)}%` }} />
      </div>
      <span className="w-9 text-right font-mono text-[10px] tabular-nums text-[var(--aegis-text-secondary)]">
        {pct}%
      </span>
    </div>
  );
}

export interface AssetDetailDrawerProps {
  runId: string;
  node: GraphNodeV1;
  disclosed: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Deep-dive drawer for a single asset. Degrades gracefully to graph-store data (label, type,
 * risk/criticality, fog-of-war disclosure state) until the console asset-detail endpoint
 * lands, and carries the full operator action menu so containment can be ordered from the
 * dive. Undisclosed assets are shown as such rather than leaking their true state.
 */
export function AssetDetailDrawer({
  runId,
  node,
  disclosed,
  open,
  onOpenChange,
}: AssetDetailDrawerProps) {
  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent data-testid="asset-detail-drawer">
        <DrawerHeader>
          <div className="flex items-center gap-2">
            <DrawerTitle>{node.label}</DrawerTitle>
            <Badge variant="outline">{node.assetType}</Badge>
          </div>
          <DrawerDescription>
            <code className="font-mono text-[10px] text-[var(--aegis-text-secondary)]">
              {node.id}
            </code>
          </DrawerDescription>
        </DrawerHeader>

        <div className="flex flex-col gap-4 px-5 pb-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className={cn(!disclosed && 'opacity-70')}>
              {disclosed ? node.status.replace(/_/g, ' ') : 'not yet detected'}
            </Badge>
            {!disclosed ? (
              <span className="text-[10px] text-[var(--aegis-text-muted)]">
                Fog of war — true state is not confirmed until detected.
              </span>
            ) : null}
          </div>

          <div className="flex flex-col gap-2 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-3 py-3">
            <StatBar label="Risk" value={node.riskScore} />
            <StatBar label="Criticality" value={node.criticality} />
          </div>

          <div className="flex flex-col gap-2">
            <p className="font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
              Direct action
            </p>
            <AssetActionMenu runId={runId} assetId={node.id} assetLabel={node.label} />
            <p className="text-[10px] leading-4 text-[var(--aegis-text-muted)]">
              Routed through the same policy pipeline as agent proposals. Class 2/3 actions ask you
              to confirm the consequences.
            </p>
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  );
}

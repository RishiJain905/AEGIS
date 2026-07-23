'use client';

import { useEffect, useRef, useState } from 'react';

import type { GraphSnapshotV1 } from '@aegis/contracts-ts';
import { cn, useReducedMotion } from '@aegis/ui';

/** How long a reveal stays highlighted in the chrome before fading back to calm. */
const REVEAL_WINDOW_MS = 6_000;

interface RevealAnnouncerProps {
  nodes: GraphSnapshotV1['nodes'];
  /** Bumped by the live-run provider whenever the graph converges (incl. reveal resyncs). */
  revision: number;
}

/**
 * The fog-of-war reveal moment, rendered accessibly at the graph chrome.
 *
 * When an asset's disclosure flips (undisclosed -> disclosed, which the live-run provider
 * converges by resyncing the now-truthful snapshot on a reveal event), this surfaces a loud
 * "DETECTION" pulse naming the revealed assets plus an assertive aria-live announcement. The
 * node's own status colour already changes on the canvas, so the state change is visible even
 * under reduced motion — where the pulse animation is suppressed but the banner still appears.
 *
 * Kept out of the Sigma shader pipeline deliberately: the in-canvas node halo is a node-program
 * concern (Phase 4), and the shared render path must not be destabilised for the reveal beat.
 */
export function RevealAnnouncer({ nodes, revision }: RevealAnnouncerProps) {
  const reducedMotion = useReducedMotion();
  // Last-known disclosure per node id. Seeded on first sight so the initial snapshot does not
  // fire a burst of "reveals" for assets that were already disclosed when the operator arrived.
  const disclosureRef = useRef<Map<string, boolean> | null>(null);
  const [revealed, setRevealed] = useState<{ id: string; label: string }[]>([]);

  useEffect(() => {
    const previous = disclosureRef.current;
    const next = new Map<string, boolean>();
    const justRevealed: { id: string; label: string }[] = [];
    for (const node of nodes) {
      const disclosed = node.disclosed !== false;
      next.set(node.id, disclosed);
      if (previous) {
        const was = previous.get(node.id);
        // A flip to disclosed on a node that is no longer "normal" is a detection beat.
        if (was === false && disclosed && node.status !== 'normal') {
          justRevealed.push({ id: node.id, label: node.label });
        }
      }
    }
    disclosureRef.current = next;
    if (previous && justRevealed.length > 0) {
      setRevealed(justRevealed);
    }
    // Depend on revision so a resync-driven snapshot swap re-runs the comparison.
  }, [nodes, revision]);

  useEffect(() => {
    if (revealed.length === 0) {
      return;
    }
    const timer = window.setTimeout(() => {
      setRevealed([]);
    }, REVEAL_WINDOW_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [revealed]);

  const message =
    revealed.length > 0
      ? `Detection: ${revealed.map((r) => r.label).join(', ')} now visible.`
      : '';

  return (
    <>
      <span className="sr-only" role="status" aria-live="assertive" data-testid="reveal-announcer">
        {message}
      </span>
      {revealed.length > 0 ? (
        <div
          className={cn(
            'mb-3 flex items-center gap-2 rounded-[var(--aegis-radius-md)] border border-[color-mix(in_srgb,var(--aegis-risk-critical)_60%,transparent)] bg-[color-mix(in_srgb,var(--aegis-risk-critical)_12%,var(--aegis-surface-elevated))] px-3 py-2',
            reducedMotion ? '' : 'animate-pulse',
          )}
          data-testid="reveal-pulse"
        >
          <span className="rounded-[var(--aegis-radius-sm)] bg-[var(--aegis-risk-critical)] px-1.5 py-0.5 font-[family-name:var(--aegis-font-display)] text-[9px] font-bold uppercase tracking-[0.14em] text-[var(--aegis-surface-base)]">
            Detection
          </span>
          <span className="min-w-0 flex-1 truncate text-xs text-[var(--aegis-text-primary)]">
            {revealed.map((r) => r.label).join(', ')} — now visible on the board.
          </span>
        </div>
      ) : null}
    </>
  );
}

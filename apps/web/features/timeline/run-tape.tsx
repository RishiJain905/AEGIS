'use client';

import { useEffect, useMemo, useRef, type PointerEvent as ReactPointerEvent } from 'react';

import { cn } from '@aegis/ui';

import { useLiveRun } from '@/features/live-run/live-run-provider';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

/** Vertical travel (px) before a grab-handle drag commits to opening or closing. */
export const TAPE_DRAG_THRESHOLD_PX = 24;

/**
 * Interpret a grab-handle drag: up past the threshold opens the chronicle, down past it
 * closes, anything less is noise. Pure so the gesture arithmetic is testable without
 * synthesizing pointer streams.
 */
export function interpretTapeDrag(deltaY: number): 'open' | 'close' | null {
  if (deltaY <= -TAPE_DRAG_THRESHOLD_PX) {
    return 'open';
  }
  if (deltaY >= TAPE_DRAG_THRESHOLD_PX) {
    return 'close';
  }
  return null;
}

/** Beat colour by the status the event carried, so a red run of beats reads at a glance. */
const STATUS_COLOR: Record<string, string> = {
  normal: 'var(--aegis-status-normal)',
  running: 'var(--aegis-status-normal)',
  suspicious: 'var(--aegis-status-suspicious)',
  under_investigation: 'var(--aegis-status-under-investigation)',
  paused: 'var(--aegis-status-under-investigation)',
  contained: 'var(--aegis-status-contained)',
  stopped: 'var(--aegis-status-contained)',
  compromised: 'var(--aegis-status-compromised)',
};

function beatColor(status: string): string {
  return STATUS_COLOR[status] ?? 'var(--aegis-border-strong)';
}

function clockOf(timestamp: string): string {
  return /T(\d{2}:\d{2}:\d{2})/.exec(timestamp)?.[1] ?? timestamp;
}

/**
 * The run tape — a single strip along the foot of the stage that shows the run's tempo:
 * one tick per significant event, coloured by the status it carried, oldest to newest.
 * A dense band of red ticks is an attack accelerating; a quiet tape is a quiet floor.
 *
 * It replaces the old full-width Timeline card, which was a second, worse copy of the ops
 * feed. The tape keeps the one thing a vertical feed cannot give — position and density
 * across the whole run — plus a probe: click a tick to pin its label and sim time in the
 * readout. Live time-travel belongs to the replay route, so the tape does not pretend to
 * scrub the simulation.
 */
export interface RunTapeProps {
  /**
   * `panel` (default) renders the tape as its own bordered strip; `console` drops the
   * outer chrome so it fuses into the cockpit console band, which owns the frame.
   */
  chrome?: 'panel' | 'console';
  /**
   * When set, the tape is also the Chronicle's handle: a labelled chevron beside the
   * readout is the primary affordance, and a grab handle above the strip supports
   * drag-up/drag-down as a pointer enhancement. Tick clicks are untouched either way —
   * the handle is a distinct hit target, so probing and dragging can never collide.
   */
  chronicle?: { open: boolean; setOpen: (open: boolean) => void };
}

export function RunTape({ chrome = 'panel', chronicle }: RunTapeProps) {
  const liveRun = useLiveRun();
  const cursorSequence = useWorkspaceUiStore((state) => state.workspace.timelineCursorSequence);
  const setCursorSequence = useWorkspaceUiStore((state) => state.setTimelineCursorSequence);
  const trackRef = useRef<HTMLDivElement>(null);

  const isLive = liveRun !== null && liveRun.isLiveMode;
  const entries = useMemo(() => (isLive ? liveRun.state.timelineEntries : []), [isLive, liveRun]);
  const latest = entries.at(-1) ?? null;
  const pinned = entries.find((entry) => entry.sequence === cursorSequence) ?? null;
  const readout = pinned ?? latest;

  // Follow the newest beat unless the operator has pinned one to inspect.
  useEffect(() => {
    if (pinned || !trackRef.current) {
      return;
    }
    trackRef.current.scrollLeft = trackRef.current.scrollWidth;
  }, [entries.length, pinned]);

  // Grab-handle drag (pointer enhancement only; the chevron and `T` are the accessible
  // paths). Window-level move/up listeners so the gesture survives leaving the handle.
  const dragStartYRef = useRef<number | null>(null);
  const handleGrabPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!chronicle) {
      return;
    }
    event.preventDefault();
    dragStartYRef.current = event.clientY;
    const onMove = (move: globalThis.PointerEvent) => {
      const startY = dragStartYRef.current;
      if (startY === null) {
        return;
      }
      const verdict = interpretTapeDrag(move.clientY - startY);
      if (verdict === 'open' && !chronicle.open) {
        chronicle.setOpen(true);
        finish();
      } else if (verdict === 'close' && chronicle.open) {
        chronicle.setOpen(false);
        finish();
      }
    };
    const finish = () => {
      dragStartYRef.current = null;
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', finish);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', finish);
  };

  return (
    <div
      className={cn(
        'relative flex min-w-0 shrink-0 items-center gap-3',
        chrome === 'panel' &&
          'rounded-[var(--aegis-radius-lg)] border border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_78%,transparent)] px-3 py-2 shadow-[var(--aegis-shadow-control)] backdrop-blur-xl',
      )}
      data-testid="run-tape"
    >
      {chronicle ? (
        <div
          aria-hidden="true"
          data-testid="chronicle-grab"
          onPointerDown={handleGrabPointerDown}
          className="absolute -top-2.5 left-1/2 flex h-4 w-20 -translate-x-1/2 cursor-grab touch-none items-center justify-center"
        >
          <span className="h-1 w-12 rounded-full bg-[var(--aegis-border-strong)]" />
        </div>
      ) : null}
      <span className="shrink-0 font-[family-name:var(--aegis-font-display)] text-[0.625rem] font-semibold uppercase tracking-[0.16em] text-[var(--aegis-text-muted)]">
        Run tape
      </span>

      <div
        ref={trackRef}
        role="group"
        aria-label="Run event tape"
        className="flex min-w-0 flex-1 items-end gap-[3px] overflow-x-auto py-1"
      >
        {entries.length === 0 ? (
          <span className="text-xs text-[var(--aegis-text-muted)]">
            {isLive ? 'Waiting for the first beat…' : 'No active run.'}
          </span>
        ) : (
          entries.map((entry) => {
            const active = entry.sequence === cursorSequence;
            return (
              <button
                key={entry.sequence}
                type="button"
                data-testid={`run-tape-beat-${String(entry.sequence)}`}
                aria-pressed={active}
                aria-label={`Sequence ${String(entry.sequence)} · ${entry.label}`}
                title={`${clockOf(entry.timestamp)} · ${entry.label}`}
                onClick={() => {
                  setCursorSequence(active ? null : entry.sequence);
                }}
                className={cn(
                  'h-6 w-[5px] shrink-0 rounded-full opacity-70 transition-[opacity,transform] hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--aegis-focus-ring)]',
                  active && 'h-8 opacity-100',
                )}
                style={{ backgroundColor: beatColor(entry.status) }}
              />
            );
          })
        )}
      </div>

      {/* The readout shrinks before the band does. It used to be `shrink-0` around a 16rem
          label, so below ~1200px it pushed the chronicle control past the viewport and the
          whole page scrolled sideways. Its prose gives way first; the clock and the
          chronicle control keep their size, because they are the parts that get used. */}
      <div
        className="flex min-w-0 shrink items-center gap-3 border-l border-[var(--aegis-border-subtle)] pl-3"
        data-testid="run-tape-readout"
      >
        {readout ? (
          <>
            <span className="min-w-0 max-w-[16rem] shrink truncate text-xs text-[var(--aegis-text-secondary)]">
              {readout.label}
            </span>
            <span className="shrink-0 font-[family-name:var(--aegis-font-mono)] text-[0.6875rem] tabular-nums text-[var(--aegis-text-muted)]">
              {clockOf(readout.timestamp)} · SEQ {readout.sequence}
            </span>
          </>
        ) : (
          <span className="shrink-0 font-[family-name:var(--aegis-font-mono)] text-[0.6875rem] text-[var(--aegis-text-muted)]">
            SEQ —
          </span>
        )}
        {pinned ? (
          <button
            type="button"
            data-testid="run-tape-unpin"
            onClick={() => {
              setCursorSequence(null);
            }}
            className="shrink-0 rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)] transition-colors hover:border-[var(--aegis-border-strong)] hover:text-[var(--aegis-text-primary)]"
          >
            Follow live
          </button>
        ) : null}
        {chronicle ? (
          <button
            type="button"
            data-testid="chronicle-toggle"
            aria-expanded={chronicle.open}
            aria-label={chronicle.open ? 'Close chronicle' : 'Open chronicle'}
            title={`${chronicle.open ? 'Close' : 'Open'} chronicle (T)`}
            onClick={() => {
              chronicle.setOpen(!chronicle.open);
            }}
            className="flex shrink-0 items-center gap-1.5 rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)] transition-colors hover:border-[var(--aegis-border-strong)] hover:text-[var(--aegis-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--aegis-focus-ring)]"
          >
            Chronicle
            <svg
              aria-hidden="true"
              viewBox="0 0 12 12"
              className={cn('h-2.5 w-2.5 transition-transform', chronicle.open && 'rotate-180')}
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
            >
              <path d="m2.5 7.5 3.5-3.5 3.5 3.5" />
            </svg>
          </button>
        ) : null}
      </div>
    </div>
  );
}

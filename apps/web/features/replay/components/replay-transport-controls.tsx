'use client';

import { Button } from '@aegis/ui';

import { nextSpeed, previousSpeed, REPLAY_SPEEDS } from '@/features/replay/lib/playback';
import { useReplay } from '@/features/replay/replay-provider';
import { useReplayStore } from '@/stores/replay-store';

export function ReplayTransportControls() {
  const replay = useReplay();
  const cursor = useReplayStore((state) => state.cursor);
  const minSequence = useReplayStore((state) => state.minSequence);
  const maxSequence = useReplayStore((state) => state.maxSequence);
  const playbackStatus = useReplayStore((state) => state.playbackStatus);
  const speed = useReplayStore((state) => state.speed);
  const reducedMotion = useReplayStore((state) => state.reducedMotion);
  const loadStatus = useReplayStore((state) => state.loadStatus);
  const setCursorSequence = useReplayStore((state) => state.setCursorSequence);
  const setPlaybackStatus = useReplayStore((state) => state.setPlaybackStatus);
  const setSpeed = useReplayStore((state) => state.setSpeed);
  const step = useReplayStore((state) => state.step);
  const jumpToMin = useReplayStore((state) => state.jumpToMin);
  const jumpToMax = useReplayStore((state) => state.jumpToMax);

  if (!cursor) {
    return null;
  }

  const disabled = loadStatus === 'unavailable' || loadStatus === 'error';
  const effectiveMax = Math.max(minSequence, maxSequence);

  return (
    <section
      className="flex flex-col gap-3 rounded-md border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-elevated)] p-3"
      data-testid="replay-transport-controls"
      aria-label="Replay transport controls"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-baseline gap-2" data-testid="replay-position-readout">
          <span className="font-mono text-lg text-[var(--aegis-text-primary)]">
            {cursor.sequence}
          </span>
          <span className="text-xs text-[var(--aegis-text-secondary)]">
            of {effectiveMax} · range {minSequence}–{effectiveMax}
          </span>
        </div>
        <span
          className="rounded border border-[var(--aegis-border-subtle)] px-2 py-0.5 text-xs uppercase tracking-wide text-[var(--aegis-text-secondary)]"
          data-testid="replay-load-status"
          role="status"
          aria-live="polite"
        >
          {loadStatus === 'loading'
            ? 'Reconstructing…'
            : loadStatus === 'ready'
              ? 'Ready'
              : loadStatus === 'unavailable'
                ? 'Unavailable'
                : loadStatus === 'error'
                  ? 'Error'
                  : 'Idle'}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          data-testid="replay-jump-start"
          disabled={disabled}
          onClick={jumpToMin}
        >
          Start
        </Button>
        <Button
          variant="outline"
          size="sm"
          data-testid="replay-step-back"
          disabled={disabled}
          onClick={() => {
            step(-1);
          }}
        >
          Step −
        </Button>
        <Button
          variant="secondary"
          size="sm"
          data-testid="replay-play-pause"
          aria-pressed={playbackStatus === 'playing'}
          disabled={disabled || reducedMotion}
          onClick={() => {
            setPlaybackStatus(playbackStatus === 'playing' ? 'paused' : 'playing');
          }}
        >
          {playbackStatus === 'playing' ? 'Pause' : 'Play'}
        </Button>
        <Button
          variant="outline"
          size="sm"
          data-testid="replay-step-forward"
          disabled={disabled}
          onClick={() => {
            step(1);
          }}
        >
          Step +
        </Button>
        <Button
          variant="outline"
          size="sm"
          data-testid="replay-jump-end"
          disabled={disabled}
          onClick={jumpToMax}
        >
          End
        </Button>
        <Button
          variant="outline"
          size="sm"
          data-testid="replay-speed-down"
          disabled={disabled}
          onClick={() => {
            setSpeed(previousSpeed(speed));
          }}
        >
          Speed −
        </Button>
        <span
          className="rounded border border-[var(--aegis-border-subtle)] px-2 py-1 font-mono text-xs"
          data-testid="replay-speed-label"
        >
          {speed}
        </span>
        <Button
          variant="outline"
          size="sm"
          data-testid="replay-speed-up"
          disabled={disabled}
          onClick={() => {
            setSpeed(nextSpeed(speed));
          }}
        >
          Speed +
        </Button>
        {REPLAY_SPEEDS.map((value) => (
          <Button
            key={value}
            variant={speed === value ? 'secondary' : 'ghost'}
            size="sm"
            data-testid={`replay-speed-${value}`}
            aria-pressed={speed === value}
            disabled={disabled}
            onClick={() => {
              setSpeed(value);
            }}
          >
            {value}
          </Button>
        ))}
        <Button
          variant="outline"
          size="sm"
          data-testid="return-to-live"
          className="ml-auto"
          onClick={() => {
            replay?.returnToLive();
          }}
        >
          Return to live
        </Button>
      </div>

      <label className="flex flex-col gap-1 text-xs text-[var(--aegis-text-secondary)]">
        Timeline scrubber
        <input
          type="range"
          min={minSequence}
          max={Math.max(minSequence, maxSequence)}
          value={cursor.sequence}
          aria-valuemin={minSequence}
          aria-valuemax={maxSequence}
          aria-valuenow={cursor.sequence}
          aria-label="Replay timeline scrubber"
          data-testid="replay-scrubber"
          disabled={disabled}
          onChange={(event) => {
            setCursorSequence(Number(event.target.value));
            setPlaybackStatus('paused');
          }}
          className="w-full accent-[var(--aegis-status-warning)]"
        />
      </label>

      {reducedMotion ? (
        <p
          className="text-xs text-[var(--aegis-text-secondary)]"
          data-testid="replay-reduced-motion"
        >
          Reduced motion is enabled. Use step and scrubber controls instead of continuous playback.
        </p>
      ) : null}

      <p className="text-xs text-[var(--aegis-text-secondary)]" role="status" aria-live="polite">
        Keyboard: Space play/pause · ←/→ step · Home/End jump · [/] speed · B next bookmark
      </p>
    </section>
  );
}

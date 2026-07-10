'use client';

import { Button, Panel } from '@aegis/ui';

import { GraphViewMode } from '@/features/cinematic-graph/contracts';
import { useCinematicGraphStore } from '@/features/cinematic-graph/stores/cinematic-graph-store';
import { useCinematicReplayStore } from '@/features/cinematic-replay/stores/cinematic-replay-store';
import { useReplayStore } from '@/stores/replay-store';

export function CinematicTransportControls() {
  const mode = useCinematicReplayStore((state) => state.mode);
  const status = useCinematicReplayStore((state) => state.status);
  const speed = useCinematicReplayStore((state) => state.speed);
  const plan = useCinematicReplayStore((state) => state.plan);
  const beatIndex = useCinematicReplayStore((state) => state.beatIndex);
  const chapterIndex = useCinematicReplayStore((state) => state.chapterIndex);
  const reducedMotion = useCinematicReplayStore((state) => state.reducedMotion);
  const captionsEnabled = useCinematicReplayStore((state) => state.captionsEnabled);
  const lastApplied = useCinematicReplayStore((state) => state.lastApplied);
  const setStatus = useCinematicReplayStore((state) => state.setStatus);
  const setSpeed = useCinematicReplayStore((state) => state.setSpeed);
  const setCaptionsEnabled = useCinematicReplayStore((state) => state.setCaptionsEnabled);
  const nextBeat = useCinematicReplayStore((state) => state.nextBeat);
  const previousBeat = useCinematicReplayStore((state) => state.previousBeat);
  const goToChapter = useCinematicReplayStore((state) => state.goToChapter);
  const takeFreeCamera = useCinematicReplayStore((state) => state.takeFreeCamera);
  const resumeCinematic = useCinematicReplayStore((state) => state.resumeCinematic);
  const goToBeat = useCinematicReplayStore((state) => state.goToBeat);

  const setCursorSequence = useReplayStore((state) => state.setCursorSequence);
  const setViewMode = useCinematicGraphStore((state) => state.setViewMode);

  if (mode !== 'cinematic') {
    return null;
  }

  const chapter = plan?.chapters[chapterIndex];
  const beat = plan?.beats[beatIndex];

  return (
    <Panel
      title="Cinematic director"
      description="Directed camera chapters over authoritative historical replay"
      data-testid="cinematic-transport-controls"
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span
          className="rounded bg-[var(--aegis-surface-elevated)] px-2 py-1 text-xs font-medium"
          data-testid="cinematic-historical-label"
        >
          Historical cinematic — read-only
        </span>
        {reducedMotion ? (
          <span
            className="rounded bg-[var(--aegis-surface-elevated)] px-2 py-1 text-xs"
            data-testid="cinematic-reduced-motion-badge"
          >
            Reduced motion: static beats
          </span>
        ) : null}
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          data-testid="cinematic-play-pause"
          aria-pressed={status === 'playing'}
          onClick={() => {
            if (status === 'playing') {
              setStatus('paused');
            } else if (status === 'free_camera') {
              resumeCinematic();
            } else {
              setStatus('playing');
            }
          }}
        >
          {status === 'playing' ? 'Pause' : status === 'free_camera' ? 'Resume' : 'Play'}
        </Button>
        <Button
          type="button"
          size="sm"
          data-testid="cinematic-prev-beat"
          onClick={() => {
            previousBeat();
          }}
        >
          Prev beat
        </Button>
        <Button
          type="button"
          size="sm"
          data-testid="cinematic-next-beat"
          onClick={() => {
            nextBeat();
          }}
        >
          Next beat
        </Button>
        <Button
          type="button"
          size="sm"
          data-testid="cinematic-prev-chapter"
          onClick={() => {
            goToChapter(chapterIndex - 1);
          }}
        >
          Prev chapter
        </Button>
        <Button
          type="button"
          size="sm"
          data-testid="cinematic-next-chapter"
          onClick={() => {
            goToChapter(chapterIndex + 1);
          }}
        >
          Next chapter
        </Button>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          data-testid="cinematic-free-camera"
          aria-pressed={status === 'free_camera'}
          onClick={() => {
            takeFreeCamera();
          }}
        >
          Free camera
        </Button>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          data-testid="cinematic-open-2d"
          onClick={() => {
            if (beat) {
              setCursorSequence(beat.sequence, beat.provenance.incidentId ?? null);
            }
            setViewMode(GraphViewMode.TWO_D);
            setStatus('paused');
          }}
        >
          Open in 2D analysis
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          data-testid="cinematic-captions-toggle"
          aria-pressed={captionsEnabled}
          onClick={() => {
            setCaptionsEnabled(!captionsEnabled);
          }}
        >
          Captions {captionsEnabled ? 'on' : 'off'}
        </Button>
      </div>

      <div className="mb-3 flex flex-wrap gap-2" data-testid="cinematic-speed-controls">
        {(['0.5x', '1x', '2x', '4x'] as const).map((value) => (
          <Button
            key={value}
            type="button"
            size="sm"
            variant={speed === value ? 'default' : 'secondary'}
            data-testid={`cinematic-speed-${value}`}
            onClick={() => {
              setSpeed(value);
            }}
          >
            {value}
          </Button>
        ))}
        <span
          className="text-xs text-[var(--aegis-text-secondary)]"
          data-testid="cinematic-speed-label"
        >
          {speed}
        </span>
      </div>

      <div className="space-y-1 text-sm" data-testid="cinematic-beat-meta">
        <p data-testid="cinematic-chapter-label">
          Chapter {chapterIndex + 1}/{plan?.chapters.length ?? 0}: {chapter?.title ?? '—'}
        </p>
        <p data-testid="cinematic-beat-label">
          Beat {beatIndex + 1}/{plan?.beats.length ?? 0}: {beat?.kind ?? '—'} @ seq{' '}
          {beat?.sequence ?? '—'}
        </p>
        {captionsEnabled && lastApplied ? (
          <p
            className="rounded border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-elevated)] p-2"
            data-testid="cinematic-caption"
          >
            {lastApplied.caption}
          </p>
        ) : null}
      </div>

      {plan ? (
        <ol
          className="mt-3 max-h-40 space-y-1 overflow-auto text-xs"
          data-testid="cinematic-chapter-rail"
        >
          {plan.chapters.map((item, index) => (
            <li key={item.id}>
              <button
                type="button"
                className={`w-full rounded px-2 py-1 text-left ${
                  index === chapterIndex
                    ? 'bg-[var(--aegis-surface-elevated)] font-medium'
                    : 'hover:bg-[var(--aegis-surface-elevated)]'
                }`}
                data-testid={`cinematic-chapter-${item.id}`}
                onClick={() => goToChapter(index)}
              >
                {item.order + 1}. {item.title} ({item.fromSequence}–{item.toSequence})
              </button>
            </li>
          ))}
        </ol>
      ) : null}

      {plan ? (
        <div className="mt-2">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            data-testid="cinematic-restart"
            onClick={() => {
              goToBeat(0);
              setStatus('paused');
            }}
          >
            Restart chapters
          </Button>
        </div>
      ) : null}
    </Panel>
  );
}

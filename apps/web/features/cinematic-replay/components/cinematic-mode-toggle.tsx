'use client';

import { Button } from '@aegis/ui';

import { GraphViewMode } from '@/features/cinematic-graph/contracts';
import { useCinematicGraphStore } from '@/features/cinematic-graph/stores/cinematic-graph-store';
import { useCinematicReplayStore } from '@/features/cinematic-replay/stores/cinematic-replay-store';
import { useReplayStore } from '@/stores/replay-store';

export function CinematicModeToggle() {
  const mode = useCinematicReplayStore((state) => state.mode);
  const setMode = useCinematicReplayStore((state) => state.setMode);
  const setStatus = useCinematicReplayStore((state) => state.setStatus);
  const clear = useCinematicReplayStore((state) => state.clear);
  const cursor = useReplayStore((state) => state.cursor);
  const setViewMode = useCinematicGraphStore((state) => state.setViewMode);

  const isCinematic = mode === 'cinematic';

  return (
    <div className="flex items-center gap-2" data-testid="cinematic-mode-toggle">
      <Button
        type="button"
        size="sm"
        variant={isCinematic ? 'secondary' : 'default'}
        data-testid="cinematic-mode-normal"
        aria-pressed={!isCinematic}
        onClick={() => {
          // Preserve replay cursor/state; only leave cinematic presentation
          setMode('normal');
          setStatus('idle');
          setViewMode(GraphViewMode.TWO_D);
        }}
      >
        Normal replay
      </Button>
      <Button
        type="button"
        size="sm"
        variant={isCinematic ? 'default' : 'secondary'}
        data-testid="cinematic-mode-cinematic"
        aria-pressed={isCinematic}
        onClick={() => {
          setMode('cinematic');
          setStatus('paused');
        }}
      >
        Cinematic replay
      </Button>
      {cursor ? (
        <span
          className="text-xs text-[var(--aegis-text-secondary)]"
          data-testid="cinematic-mode-cursor"
        >
          Cursor seq {cursor.sequence}
        </span>
      ) : null}
      {isCinematic ? (
        <Button
          type="button"
          size="sm"
          variant="ghost"
          data-testid="cinematic-mode-reset-plan"
          onClick={() => {
            clear();
            setMode('cinematic');
            setStatus('paused');
          }}
        >
          Rebuild plan
        </Button>
      ) : null}
    </div>
  );
}

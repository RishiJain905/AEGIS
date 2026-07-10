'use client';

import { Button, Panel } from '@aegis/ui';

import { GraphViewMode } from '@/features/cinematic-graph/contracts';
import { useCinematicGraphStore } from '@/features/cinematic-graph/stores/cinematic-graph-store';
import { useCinematicReplayStore } from '@/features/cinematic-replay/stores/cinematic-replay-store';
import { useReplayStore } from '@/stores/replay-store';

/**
 * Accessibility fallback: exposes the same critical incident information
 * without requiring 3D/camera motion.
 */
export function CinematicAccessibilityFallback() {
  const mode = useCinematicReplayStore((state) => state.mode);
  const plan = useCinematicReplayStore((state) => state.plan);
  const beatIndex = useCinematicReplayStore((state) => state.beatIndex);
  const chapterIndex = useCinematicReplayStore((state) => state.chapterIndex);
  const lastApplied = useCinematicReplayStore((state) => state.lastApplied);
  const lastError = useCinematicReplayStore((state) => state.lastError);
  const planWarnings = useCinematicReplayStore((state) => state.planWarnings);
  const reducedMotion = useCinematicReplayStore((state) => state.reducedMotion);
  const goToBeat = useCinematicReplayStore((state) => state.goToBeat);
  const setStatus = useCinematicReplayStore((state) => state.setStatus);

  const setCursorSequence = useReplayStore((state) => state.setCursorSequence);
  const setViewMode = useCinematicGraphStore((state) => state.setViewMode);

  if (mode !== 'cinematic') {
    return null;
  }

  const chapter = plan?.chapters[chapterIndex];
  const beat = plan?.beats[beatIndex];

  return (
    <Panel
      title="Cinematic accessibility"
      description="Critical incident information without requiring 3D motion"
      data-testid="cinematic-a11y-fallback"
    >
      {lastError ? (
        <div
          className="mb-3 rounded border border-[var(--aegis-border-danger)] p-2 text-sm"
          data-testid="cinematic-error"
          role="alert"
        >
          <p className="font-medium">{lastError.message}</p>
          <p className="font-mono text-xs" data-testid="cinematic-error-code">
            {lastError.code}
          </p>
        </div>
      ) : null}

      {reducedMotion ? (
        <p
          className="mb-2 text-xs text-[var(--aegis-text-secondary)]"
          data-testid="cinematic-a11y-reduced-motion"
        >
          Reduced motion is on. Camera easing is disabled; use the beat list to navigate.
        </p>
      ) : null}

      <div className="mb-3 space-y-1 text-sm">
        <p data-testid="cinematic-a11y-chapter">
          <strong>Chapter:</strong> {chapter?.title ?? 'Unavailable'} — {chapter?.summary ?? ''}
        </p>
        <p data-testid="cinematic-a11y-beat">
          <strong>Beat:</strong> {beat?.kind ?? '—'} @ sequence {beat?.sequence ?? '—'}
        </p>
        <p data-testid="cinematic-a11y-caption">{lastApplied?.caption ?? beat?.caption ?? '—'}</p>
        <p data-testid="cinematic-a11y-entities">
          <strong>Entities:</strong>{' '}
          {beat && beat.entityIds.length > 0 ? beat.entityIds.join(', ') : 'none'}
        </p>
        <p data-testid="cinematic-a11y-provenance">
          <strong>Provenance:</strong> seq {beat?.provenance.sequence ?? '—'} · source{' '}
          {beat?.provenance.source ?? '—'}
          {beat?.provenance.incidentId ? ` · ${beat.provenance.incidentId}` : ''}
        </p>
      </div>

      <Button
        type="button"
        size="sm"
        data-testid="cinematic-a11y-open-2d"
        onClick={() => {
          if (beat) {
            setCursorSequence(beat.sequence, beat.provenance.incidentId ?? null);
          }
          setViewMode(GraphViewMode.TWO_D);
          setStatus('paused');
        }}
      >
        Jump to 2D analysis at this beat
      </Button>

      {plan ? (
        <ol
          className="mt-3 max-h-56 space-y-1 overflow-auto text-xs"
          data-testid="cinematic-a11y-beat-list"
        >
          {plan.beats.map((item, index) => (
            <li key={item.id}>
              <button
                type="button"
                className={`w-full rounded px-2 py-1 text-left ${
                  index === beatIndex
                    ? 'bg-[var(--aegis-surface-elevated)] font-medium'
                    : 'hover:bg-[var(--aegis-surface-elevated)]'
                }`}
                data-testid={`cinematic-a11y-beat-${item.id}`}
                onClick={() => goToBeat(index)}
              >
                [{item.sequence}] {item.kind}: {item.caption}
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <p
          className="mt-2 text-sm text-[var(--aegis-text-secondary)]"
          data-testid="cinematic-a11y-empty"
        >
          No cinematic plan available yet.
        </p>
      )}

      {planWarnings.length > 0 ? (
        <ul
          className="mt-2 list-disc pl-4 text-xs text-[var(--aegis-text-secondary)]"
          data-testid="cinematic-plan-warnings"
        >
          {planWarnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
    </Panel>
  );
}

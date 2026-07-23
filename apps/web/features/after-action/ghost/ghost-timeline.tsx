'use client';

/**
 * Ghost divergence timeline — the alternate beats the engine produced after the fork.
 *
 * This reuses the adversary-dossier attacker-lane row look (each beat is an attacker-tinted
 * card carrying a time offset + label + optional asset/status), duplicated here rather than
 * exported from the dossier: the two surfaces render different data and the repo convention
 * favours a self-contained ~70-line row over cross-feature coupling. Offsets are measured
 * from the divergence point so the operator reads "time since I forked".
 */

import type { GhostTimelineBeatV1 } from '@aegis/contracts-ts';
import { EmptyState, cn, typographyTokens } from '@aegis/ui';

import { secondsBetween } from '../dossier/assemble-dossier';

/** `+MM:SS` / `+H:MM:SS` offset from the divergence sim time (never negative). */
export function offsetLabel(startSimTime: string | undefined, simTime: string): string {
  if (!startSimTime) {
    return '';
  }
  const seconds = secondsBetween(startSimTime, simTime);
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const mm = String(m).padStart(2, '0');
  const ss = String(s).padStart(2, '0');
  return h > 0 ? `+${String(h)}:${mm}:${ss}` : `+${mm}:${ss}`;
}

function GhostBeatRow({
  beat,
  startSimTime,
}: {
  beat: GhostTimelineBeatV1;
  startSimTime: string | undefined;
}) {
  const offset = offsetLabel(startSimTime, beat.simTime);
  return (
    <li
      className="flex justify-start py-1.5"
      data-testid="ghost-timeline-beat"
      data-kind={beat.kind}
    >
      <div className="flex max-w-[26rem] flex-col gap-1 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-status-compromised)]/30 bg-[var(--aegis-status-compromised-bg)]/50 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[0.65rem] text-[var(--aegis-text-muted)] tabular-nums">
            {offset || `seq ${String(beat.sequence)}`}
          </span>
          <span className="text-sm font-medium leading-5 text-[var(--aegis-text-primary)]">
            {beat.label}
          </span>
        </div>
        {beat.assetId || beat.status ? (
          <span className="text-[0.7rem] text-[var(--aegis-status-suspicious)]">
            {[beat.assetId, beat.status].filter(Boolean).join(' · ')}
          </span>
        ) : null}
      </div>
    </li>
  );
}

export function GhostTimeline({
  beats,
  startSimTime,
}: {
  beats: readonly GhostTimelineBeatV1[];
  startSimTime: string | undefined;
}) {
  if (beats.length === 0) {
    return (
      <EmptyState
        title="No divergent beats"
        description="The alternate timeline produced no new events after the fork."
        data-testid="ghost-timeline-empty"
      />
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <span
        className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-status-compromised)]')}
        aria-hidden="true"
      >
        Ghost world
      </span>
      <ol
        className="flex flex-col gap-y-0.5"
        data-testid="ghost-timeline"
        aria-label="Alternate timeline beats after the divergence point"
      >
        {beats.map((beat) => (
          <GhostBeatRow
            key={`${String(beat.sequence)}-${beat.label}`}
            beat={beat}
            startSimTime={startSimTime}
          />
        ))}
      </ol>
    </div>
  );
}

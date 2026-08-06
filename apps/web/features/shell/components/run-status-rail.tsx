'use client';

import { ConnectionHealthState } from '@aegis/contracts-ts';
import { cn } from '@aegis/ui';

import { resolveConnectionState, type ConnectionStateInput } from '@/lib/realtime/connection-state';
import { describeRunOutcome } from '@/lib/run-status';

/**
 * The mission rail — four instruments, four facts, one shared vocabulary.
 *
 * The old header narrated everything through one "CONTROL LINK" badge, which is how the
 * cockpit could say "Live" and "paused" in the same breath (BUG-011). Each instrument here
 * owns exactly one question and nothing else:
 *
 *   LINK    — is event delivery to *this screen* healthy?
 *   SIM     — is simulated time moving?
 *   POSTURE — how bad does the disclosed estate look?
 *   REPORT  — where does the engagement stand as a record?
 *
 * The transport controls (`LiveRunControls`) carry the same two group labels — SIM and
 * LINK — so every control is visibly wired to the instrument it changes.
 *
 * All describe* helpers are pure and exported for tests.
 */

/** Semantic tone → colour tokens shared by every instrument. */
export type InstrumentTone = 'ok' | 'info' | 'warn' | 'down' | 'held' | 'muted' | 'ended';

const TONE_COLOR: Record<InstrumentTone, string> = {
  ok: 'var(--aegis-status-normal)',
  info: 'var(--aegis-status-under-investigation)',
  warn: 'var(--aegis-status-suspicious)',
  down: 'var(--aegis-status-compromised)',
  held: 'var(--aegis-status-contained)',
  muted: 'var(--aegis-text-muted)',
  ended: 'var(--aegis-text-primary)',
};

export interface LinkReading {
  label: string;
  tone: InstrumentTone;
  /** True while the link is actively working to restore itself (motion-safe pulse). */
  pulse: boolean;
  detail: string;
}

/** One instrument reading per connection condition — the chip's half of the vocabulary. */
const LINK_READINGS: Record<string, LinkReading> = {
  [ConnectionHealthState.CONNECTED]: {
    label: 'Connected',
    tone: 'ok',
    pulse: false,
    detail: 'Live events are reaching this screen.',
  },
  // A paused simulator is a healthy link; the pause itself is the SIM instrument's fact.
  [ConnectionHealthState.SIMULATOR_PAUSED]: {
    label: 'Connected',
    tone: 'ok',
    pulse: false,
    detail: 'Live events are reaching this screen.',
  },
  [ConnectionHealthState.LOCALLY_PAUSED]: {
    label: 'Held',
    tone: 'held',
    pulse: false,
    detail: 'You are holding live updates. Resume from the Link controls to apply them.',
  },
  [ConnectionHealthState.RECONNECTING]: {
    label: 'Reconnecting',
    tone: 'warn',
    pulse: true,
    detail: 'Restoring the realtime connection.',
  },
  [ConnectionHealthState.CATCHING_UP]: {
    label: 'Syncing',
    tone: 'info',
    pulse: true,
    detail: 'Applying missed events before resuming live delivery.',
  },
  [ConnectionHealthState.SNAPSHOT_RESYNC]: {
    label: 'Syncing',
    tone: 'info',
    pulse: true,
    detail: 'Applying missed events before resuming live delivery.',
  },
  [ConnectionHealthState.GAP]: {
    label: 'Recovering',
    tone: 'warn',
    pulse: true,
    detail: 'A sequence gap is being repaired from an authoritative snapshot.',
  },
  [ConnectionHealthState.DISCONNECTED]: {
    label: 'Offline',
    tone: 'down',
    pulse: false,
    detail: 'No realtime connection. The board may lag the simulation.',
  },
  [ConnectionHealthState.STALE]: {
    label: 'Stale',
    tone: 'warn',
    pulse: false,
    detail: 'Event delivery is interrupted. Recover before trusting the live view.',
  },
};

/**
 * Describe realtime delivery — and only delivery.
 *
 * The condition comes from `resolveConnectionState`, the same call the connection banner
 * makes. That shared source is what stopped this chip reading "Connected" while the banner
 * beneath it warned the projection was stale: `isStale` is now folded into the condition
 * both surfaces render, so a stale projection reads Stale in both places or in neither.
 */
export function describeLink(input: ConnectionStateInput): LinkReading {
  const reading = resolveConnectionState(input);
  return (
    LINK_READINGS[reading.condition] ?? {
      label: 'Unknown',
      tone: 'warn',
      pulse: false,
      detail: 'Link health is unrecognized.',
    }
  );
}

export interface SimReading {
  label: string;
  /** Transport glyph — the playback grammar operators already know. */
  glyph: string;
  tone: InstrumentTone;
  terminal: boolean;
  detail: string;
}

/** Describe the simulation lifecycle — is simulated time moving, and can it still? */
export function describeSim(
  runStatus: string | undefined,
  outcome?: { outcome: string; reason: string; resolvedSimTime: string } | null,
): SimReading {
  // A terminal run's reason comes from its resolved verdict when there is one: Silent
  // Relay runs end at 00:06:15 because the attacker exfiltrated, and "the scenario ran to
  // completion" would read that fixed boundary as a premature stop. The verdict is
  // announced before the STOP, so a terminal status with an outcome always has it.
  const outcomeReading = describeRunOutcome(outcome);
  switch (runStatus) {
    case 'running':
      return {
        label: 'Running',
        glyph: '▶',
        tone: 'ok',
        terminal: false,
        detail: 'Simulated time is advancing.',
      };
    case 'paused':
      return {
        label: 'Paused',
        glyph: '❚❚',
        tone: 'warn',
        terminal: false,
        detail: 'Simulated time is frozen. Commands still execute against the frozen timeline.',
      };
    case 'completed':
      return {
        label: 'Complete',
        glyph: '■',
        tone: 'ended',
        terminal: true,
        detail: outcomeReading
          ? `${outcomeReading.detail} The timeline is read-only.`
          : 'The scenario ran to completion. The timeline is read-only.',
      };
    case 'stopped':
      return {
        label: 'Stopped',
        glyph: '■',
        tone: 'ended',
        terminal: true,
        detail: outcomeReading
          ? `${outcomeReading.detail} The timeline is read-only.`
          : 'The run was stopped. The timeline is read-only.',
      };
    case 'created':
      return {
        label: 'Standby',
        glyph: '◇',
        tone: 'muted',
        terminal: false,
        detail: 'The run exists but has not started ticking.',
      };
    default:
      return {
        label: runStatus ?? '—',
        glyph: '◇',
        tone: 'muted',
        terminal: false,
        detail: 'Simulation state is unknown.',
      };
  }
}

export type ThreatPosture = 'normal' | 'suspicious' | 'critical';

export interface PostureReading {
  posture: ThreatPosture;
  label: string;
  detail: string;
}

/**
 * Derive threat posture from the disclosed estate: the worst node status the operator can
 * currently see. Fog of war means this is honest by construction — it can only report what
 * the board itself shows.
 */
export function describePosture(nodes: readonly { status: string }[] | undefined): PostureReading {
  let suspicious = false;
  for (const node of nodes ?? []) {
    if (node.status === 'compromised') {
      return {
        posture: 'critical',
        label: 'Critical',
        detail: 'At least one asset is confirmed compromised.',
      };
    }
    if (
      node.status === 'suspicious' ||
      node.status === 'under_investigation' ||
      node.status === 'contained'
    ) {
      suspicious = true;
    }
  }
  if (suspicious) {
    return {
      posture: 'suspicious',
      label: 'Suspicious',
      detail: 'Assets are showing anomalous or contained state. Nothing confirmed compromised.',
    };
  }
  return {
    posture: 'normal',
    label: 'Normal',
    detail: 'No disclosed asset is in a degraded state.',
  };
}

const POSTURE_TOKENS: Record<ThreatPosture, { fg: string; bg: string }> = {
  normal: { fg: 'var(--aegis-status-normal)', bg: 'var(--aegis-status-normal-bg)' },
  suspicious: { fg: 'var(--aegis-status-suspicious)', bg: 'var(--aegis-status-suspicious-bg)' },
  critical: { fg: 'var(--aegis-status-compromised)', bg: 'var(--aegis-status-compromised-bg)' },
};

export interface ReportReading {
  label: string;
  tone: InstrumentTone;
  /** True once the run is terminal — the report chip's "look here" moment. */
  ready: boolean;
  detail: string;
}

/** Describe where the engagement stands as a record. */
export function describeReport(input: {
  runStatus: string | undefined;
  reportAvailable: boolean;
}): ReportReading {
  const terminal = input.runStatus === 'completed' || input.runStatus === 'stopped';
  if (!terminal) {
    return {
      label: 'Underway',
      tone: 'muted',
      ready: false,
      detail: 'The engagement is still open. The after-action report generates once it ends.',
    };
  }
  if (input.reportAvailable) {
    return {
      label: 'Report ready',
      tone: 'ended',
      ready: true,
      detail: 'The after-action report is available in the Inspector.',
    };
  }
  return {
    label: 'Debrief pending',
    tone: 'warn',
    ready: false,
    detail: 'The run has ended; the after-action report has not been generated yet.',
  };
}

function InstrumentLabel({ children }: { children: string }) {
  return (
    <span className="font-[family-name:var(--aegis-font-display)] text-[0.5625rem] font-semibold uppercase tracking-[0.18em] text-[var(--aegis-text-faint)]">
      {children}
    </span>
  );
}

export interface RunStatusRailProps {
  isLiveMode: boolean;
  connectionHealth?: string;
  connectionStatus?: string;
  /**
   * The reducer's staleness flag. Part of the LINK reading, not a separate instrument: a
   * projection known to be behind is not a connected link, whatever the socket reports.
   */
  isStale?: boolean;
  runStatus?: string;
  /** The run's resolved verdict, when the live stream has projected it. */
  runOutcome?: { outcome: string; reason: string; resolvedSimTime: string } | null;
  /** Disclosed graph nodes; posture derives from their worst status. */
  nodes?: readonly { status: string }[];
  reportAvailable?: boolean;
  /**
   * False on surfaces with no run in context (catalogue, admin). The run-scoped
   * instruments hide rather than showing placeholder facts — a rail that says
   * "Underway" about no run in particular is a lie, not a reading.
   */
  hasRun?: boolean;
}

/**
 * Renders the four instruments in reading order: LINK, SIM, POSTURE, REPORT. Terminal
 * precedence: once the run ends, SIM takes the strong filled treatment, LINK demotes to
 * muted (delivery no longer matters), and REPORT lights up when the record exists.
 */
export function RunStatusRail({
  isLiveMode,
  connectionHealth,
  connectionStatus,
  isStale,
  runStatus,
  runOutcome,
  nodes,
  reportAvailable = false,
  hasRun = true,
}: RunStatusRailProps) {
  const link = describeLink({
    isLiveMode,
    health: connectionHealth,
    connectionStatus,
    isStale,
    runStatus,
  });
  const sim = describeSim(runStatus, runOutcome);
  const posture = describePosture(nodes);
  const report = describeReport({ runStatus, reportAvailable });

  const linkColor = sim.terminal ? TONE_COLOR.muted : TONE_COLOR[link.tone];
  const postureTokens = POSTURE_TOKENS[posture.posture];

  return (
    <div
      className="flex flex-wrap items-center gap-x-3 gap-y-1.5"
      role="group"
      aria-label="Run status"
      data-testid="run-status-rail"
    >
      <div className="flex items-center gap-1.5">
        <InstrumentLabel>Link</InstrumentLabel>
        <span
          data-testid="connection-status-badge"
          title={
            sim.terminal ? 'The run has ended; live delivery is no longer in play.' : link.detail
          }
          className="flex items-center gap-1.5 font-[family-name:var(--aegis-font-mono)] text-[0.6875rem] uppercase tracking-[0.08em]"
          style={{ color: linkColor }}
        >
          <span
            aria-hidden="true"
            className={cn(
              'h-1.5 w-1.5 shrink-0 rounded-full',
              link.pulse && !sim.terminal && 'motion-safe:animate-pulse',
            )}
            style={{
              backgroundColor: linkColor,
              boxShadow: link.pulse && !sim.terminal ? `0 0 8px 0 ${linkColor}` : undefined,
            }}
          />
          {link.label}
        </span>
      </div>

      {hasRun ? (
        <>
          <div className="flex items-center gap-1.5 border-l border-[var(--aegis-border-subtle)] pl-3">
            <InstrumentLabel>Sim</InstrumentLabel>
            <span
              data-testid="run-status"
              title={sim.detail}
              className={cn(
                'flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-[family-name:var(--aegis-font-display)] text-[0.625rem] font-semibold uppercase tracking-[0.13em]',
                sim.terminal
                  ? 'border-[var(--aegis-border-strong)] bg-[var(--aegis-surface-raised)] text-[var(--aegis-text-primary)]'
                  : 'border-transparent',
              )}
              style={sim.terminal ? undefined : { color: TONE_COLOR[sim.tone] }}
            >
              <span
                aria-hidden="true"
                className="font-[family-name:var(--aegis-font-mono)] text-[0.5rem] leading-none"
              >
                {sim.glyph}
              </span>
              {sim.label}
            </span>
          </div>

          <div className="flex items-center gap-1.5 border-l border-[var(--aegis-border-subtle)] pl-3">
            <InstrumentLabel>Posture</InstrumentLabel>
            <span
              data-testid="threat-posture"
              data-posture={posture.posture}
              title={posture.detail}
              className={cn(
                'rounded-full px-2 py-0.5 font-[family-name:var(--aegis-font-display)] text-[0.625rem] font-semibold uppercase tracking-[0.13em]',
                posture.posture === 'critical' && 'motion-safe:animate-pulse',
              )}
              style={{ color: postureTokens.fg, backgroundColor: postureTokens.bg }}
            >
              {posture.label}
            </span>
          </div>

          <div className="flex items-center gap-1.5 border-l border-[var(--aegis-border-subtle)] pl-3">
            <InstrumentLabel>Report</InstrumentLabel>
            <span
              data-testid="run-outcome"
              title={report.detail}
              className={cn(
                'font-[family-name:var(--aegis-font-mono)] text-[0.6875rem] uppercase tracking-[0.08em]',
                report.ready && 'font-semibold',
              )}
              style={{
                color: report.ready ? 'var(--aegis-accent-strong)' : TONE_COLOR[report.tone],
              }}
            >
              {report.label}
            </span>
          </div>
        </>
      ) : null}
    </div>
  );
}

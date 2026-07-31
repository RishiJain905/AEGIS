'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useQueryClient } from '@tanstack/react-query';

import { ConnectionHealthState } from '@aegis/contracts-ts';
import { Alert, Badge, Button, cn, getMotionTransition, useReducedMotion } from '@aegis/ui';

import { useLiveRun } from '@/features/live-run/live-run-provider';
import type { ConnectionStatus } from '@/lib/api';
import { useConnectionStatus } from '@/features/shell/hooks/use-shell-queries';

/**
 * How long a degraded connection must persist before the operator is told about it. The
 * transport flips through `catching_up` / `snapshot_resync` constantly during healthy
 * operation (every catch-up batch, every reveal-driven resync), so anything shorter turns
 * the banner into a strobe.
 */
const APPEAR_DELAY_MS = 700;

/** Once shown, the banner holds for at least this long so recovery cannot make it blink. */
const MIN_VISIBLE_MS = 1_200;

export interface ConnectionNotice {
  /** Stable identity for the underlying condition; also exposed for tests/debugging. */
  key: string;
  variant: 'default' | 'warning';
  title: string;
  detail: string;
}

/** Also the fallback for any health value this presentation layer does not know yet. */
const STALE_NOTICE: ConnectionNotice = {
  key: 'stale',
  variant: 'warning',
  title: 'Stale state',
  detail: 'Event delivery is interrupted. Recover before trusting the live view.',
};

const LIVE_NOTICES: Record<string, ConnectionNotice> = {
  [ConnectionHealthState.STALE]: STALE_NOTICE,
  [ConnectionHealthState.DISCONNECTED]: {
    key: 'disconnected',
    variant: 'warning',
    title: 'Disconnected',
    detail: 'Displayed state may not reflect the latest simulation progress.',
  },
  [ConnectionHealthState.RECONNECTING]: {
    key: 'reconnecting',
    variant: 'warning',
    title: 'Reconnecting',
    detail: 'Restoring the realtime connection from the last processed cursor.',
  },
  [ConnectionHealthState.CATCHING_UP]: {
    key: 'catching_up',
    variant: 'default',
    title: 'Catching up',
    detail: 'Applying historical events before resuming live delivery.',
  },
  [ConnectionHealthState.SNAPSHOT_RESYNC]: {
    key: 'snapshot_resync',
    variant: 'warning',
    title: 'Resynchronizing',
    detail: 'Loading an authoritative snapshot and replaying missed events.',
  },
  [ConnectionHealthState.GAP]: {
    key: 'gap',
    variant: 'warning',
    title: 'Sequence gap',
    detail: 'Event application is paused until missing sequences are recovered.',
  },
  [ConnectionHealthState.SIMULATOR_PAUSED]: {
    key: 'simulator_paused',
    variant: 'default',
    title: 'Simulation paused',
    detail: 'The board resumes updating when the simulator does.',
  },
  [ConnectionHealthState.LOCALLY_PAUSED]: {
    key: 'locally_paused',
    variant: 'default',
    title: 'Updates paused',
    detail: 'Live updates are held locally. Resume to apply queued events.',
  },
};

const FIXTURE_NOTICES: Partial<Record<ConnectionStatus, ConnectionNotice>> = {
  offline: {
    key: 'fixture_offline',
    variant: 'warning',
    title: 'Connection offline',
    detail: 'Realtime updates are unavailable. Showing last known fixture data.',
  },
  reconnecting: {
    key: 'fixture_reconnecting',
    variant: 'default',
    title: 'Reconnecting',
    detail: 'Attempting to restore the realtime connection…',
  },
};

/**
 * The single mapping from connection state to operator-facing copy. Live runs are described
 * by the transport's own health; fixture-backed views fall back to the polled connection
 * status. Returns `null` when there is nothing worth interrupting the operator about.
 */
export function describeConnectionNotice(input: {
  isLiveMode: boolean;
  health?: string;
  isStale?: boolean;
  connectionStatus: ConnectionStatus;
}): ConnectionNotice | null {
  if (input.isLiveMode) {
    if (input.health !== undefined && input.health !== ConnectionHealthState.CONNECTED) {
      return LIVE_NOTICES[input.health] ?? STALE_NOTICE;
    }
    // Connected but the reducer still flags the projection as stale — worth saying so.
    return input.isStale === true ? STALE_NOTICE : null;
  }
  return FIXTURE_NOTICES[input.connectionStatus] ?? null;
}

/**
 * Debounce on the way in, latch on the way out.
 *
 * `notice` must be referentially stable while the underlying condition is unchanged. The
 * appearance timer is armed on the transition from "healthy" to "degraded" and is *not*
 * restarted when the condition changes shape mid-flight — a link that oscillates between
 * `reconnecting` and `gap` has still been degraded the whole time, and should be reported.
 */
export function useNoticeHysteresis(notice: ConnectionNotice | null): ConnectionNotice | null {
  const [visible, setVisible] = useState<ConnectionNotice | null>(null);
  const visibleRef = useRef<ConnectionNotice | null>(null);
  const shownAtRef = useRef(0);
  const noticeRef = useRef(notice);
  noticeRef.current = notice;

  const degraded = notice !== null;

  useEffect(() => {
    if (degraded) {
      if (visibleRef.current !== null) {
        // Already up; this effect run only exists to cancel a pending hide (via cleanup).
        return;
      }
      const timer = window.setTimeout(() => {
        visibleRef.current = noticeRef.current;
        shownAtRef.current = Date.now();
        setVisible(noticeRef.current);
      }, APPEAR_DELAY_MS);
      return () => {
        window.clearTimeout(timer);
      };
    }
    if (visibleRef.current === null) {
      return;
    }
    const remaining = Math.max(0, MIN_VISIBLE_MS - (Date.now() - shownAtRef.current));
    const timer = window.setTimeout(() => {
      visibleRef.current = null;
      setVisible(null);
    }, remaining);
    return () => {
      window.clearTimeout(timer);
    };
  }, [degraded]);

  // Swap the copy in place when the condition changes while the banner is already up.
  useEffect(() => {
    if (notice !== null && visibleRef.current !== null && visibleRef.current !== notice) {
      visibleRef.current = notice;
      setVisible(notice);
    }
  }, [notice]);

  return visible;
}

/**
 * The one realtime-connection surface in the shell.
 *
 * Placement is deliberately layout-neutral: the component occupies a zero-height slot
 * directly beneath the status strip and hangs its notice into the content area on an
 * absolutely positioned layer. Connection health flips several times a minute during normal
 * play, and this shell is a fixed-height cockpit on desktop — anything that takes height here
 * resizes `<main>`, which resizes the Sigma canvas and both docks, and the whole board judders.
 * The at-a-glance indicator lives in the status strip's fixed-size connection badge; this
 * banner only explains what the badge cannot.
 */
export function ConnectionHealthBanner() {
  const liveRun = useLiveRun();
  const connectionQuery = useConnectionStatus();
  const reducedMotion = useReducedMotion();
  const queryClient = useQueryClient();
  const [retrying, setRetrying] = useState(false);

  const isLiveMode = liveRun?.isLiveMode === true;
  const health = liveRun?.state.connectionHealth;
  const isStale = liveRun?.state.isStale;
  const sequence = liveRun?.state.lastAppliedSequence;
  const connectionStatus = connectionQuery.data ?? 'connected';

  const notice = useMemo(
    () =>
      describeConnectionNotice({
        isLiveMode,
        health,
        isStale,
        connectionStatus,
      }),
    [isLiveMode, health, isStale, connectionStatus],
  );
  const shown = useNoticeHysteresis(notice);

  // Manual recovery. Automatic retries deliberately slow down while an endpoint keeps
  // failing (see lib/api/retry-policy), which is right for the machine and wrong for an
  // operator who has just fixed the thing and wants to know now. Refetching the active
  // queries clears their error state on success, which is also what resets the polling
  // cadence to its healthy interval.
  const resync = liveRun?.resync;
  const handleRetry = useCallback(() => {
    setRetrying(true);
    void Promise.allSettled([
      queryClient.refetchQueries({ type: 'active' }),
      resync ? resync() : Promise.resolve(),
    ]).finally(() => {
      setRetrying(false);
    });
  }, [queryClient, resync]);

  // Entrance is opt-in per appearance so the banner fades in rather than popping over the map.
  const [entered, setEntered] = useState(false);
  useEffect(() => {
    if (shown === null) {
      setEntered(false);
      return;
    }
    setEntered(true);
  }, [shown]);

  if (shown === null) {
    return null;
  }

  return (
    <div className="relative z-20 h-0" data-testid="connection-health-banner">
      <div className="pointer-events-none absolute inset-x-0 top-0 flex justify-center px-5 pt-3 xl:px-6">
        <Alert
          variant={shown.variant}
          title={shown.title}
          role="status"
          aria-live="polite"
          data-testid="connection-banner"
          data-connection-notice={shown.key}
          className={cn(
            'pointer-events-auto w-full max-w-md shadow-[var(--aegis-shadow-panel)] backdrop-blur-xl',
            reducedMotion ? undefined : entered ? 'opacity-100' : 'translate-y-[-4px] opacity-0',
          )}
          style={
            reducedMotion
              ? undefined
              : {
                  transition: getMotionTransition(['opacity', 'transform'], 'fast'),
                }
          }
        >
          <span className="text-xs leading-4">
            {shown.detail}
            {shown.variant === 'warning' ? ' Retries are backing off.' : null}
          </span>
          {isLiveMode && sequence !== undefined ? (
            <div className="mt-2 flex items-center gap-2">
              <Badge>{`Sequence ${String(sequence)}`}</Badge>
              {isStale === true ? <Badge>Stale</Badge> : null}
            </div>
          ) : null}
          {/* Only where waiting is the alternative. A paused simulator or an in-flight
              catch-up recovers on its own, and a button that "fixes" neither is noise. */}
          {shown.variant === 'warning' ? (
            <div className="mt-2">
              <Button
                size="sm"
                variant="outline"
                onClick={handleRetry}
                disabled={retrying}
                data-testid="connection-retry-now"
              >
                {retrying ? 'Retrying…' : 'Retry now'}
              </Button>
            </div>
          ) : null}
        </Alert>
      </div>
    </div>
  );
}

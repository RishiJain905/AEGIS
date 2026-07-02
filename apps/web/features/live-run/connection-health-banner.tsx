'use client';

import { Alert, Badge } from '@aegis/ui';

import { ConnectionHealthState } from '@aegis/contracts-ts';

import { useLiveRun } from '@/features/live-run/live-run-provider';

const HEALTH_LABELS: Record<string, string> = {
  connected: 'Live connected',
  disconnected: 'Disconnected',
  reconnecting: 'Reconnecting',
  catching_up: 'Catching up',
  gap: 'Sequence gap',
  snapshot_resync: 'Resynchronizing',
  simulator_paused: 'Simulation paused',
  locally_paused: 'Updates paused',
  stale: 'Stale state',
};

const HEALTH_VARIANT: Record<string, 'default' | 'warning'> = {
  connected: 'default',
  disconnected: 'warning',
  reconnecting: 'warning',
  catching_up: 'default',
  gap: 'warning',
  snapshot_resync: 'warning',
  simulator_paused: 'default',
  locally_paused: 'default',
  stale: 'warning',
};

export function ConnectionHealthBanner() {
  const liveRun = useLiveRun();
  if (liveRun === null || !liveRun.isLiveMode) {
    return null;
  }

  const health = liveRun.state.connectionHealth;
  if (health === ConnectionHealthState.CONNECTED) {
    return null;
  }

  const label = HEALTH_LABELS[health] ?? health;
  const variant = HEALTH_VARIANT[health] ?? 'warning';

  return (
    <Alert
      variant={variant}
      title={label}
      className="mx-4 mt-3"
      data-testid="connection-health-banner"
    >
      {health === ConnectionHealthState.DISCONNECTED || health === ConnectionHealthState.STALE
        ? 'Displayed state may not reflect the latest simulation progress.'
        : null}
      {health === ConnectionHealthState.RECONNECTING
        ? 'Attempting to restore the realtime connection from the last processed cursor.'
        : null}
      {health === ConnectionHealthState.CATCHING_UP
        ? 'Applying historical events before resuming live delivery.'
        : null}
      {health === ConnectionHealthState.SNAPSHOT_RESYNC
        ? 'Loading an authoritative snapshot and replaying missed events.'
        : null}
      {health === ConnectionHealthState.GAP
        ? 'Event application is paused until missing sequences are recovered.'
        : null}
      <div className="mt-2 flex items-center gap-2">
        <Badge>{`Sequence ${String(liveRun.state.lastAppliedSequence)}`}</Badge>
        {liveRun.state.isStale ? <Badge>Stale</Badge> : null}
      </div>
    </Alert>
  );
}

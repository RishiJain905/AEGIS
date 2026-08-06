import { ConnectionHealthState } from '@aegis/contracts-ts';
import { describe, expect, it } from 'vitest';

import { resolveConnectionState, shouldNotify } from './connection-state';

const LIVE_HEALTHS = Object.values(ConnectionHealthState);

describe('resolveConnectionState', () => {
  it('reports a healthy live link as connected and says nothing about it', () => {
    const reading = resolveConnectionState({
      isLiveMode: true,
      health: ConnectionHealthState.CONNECTED,
      isStale: false,
    });
    expect(reading).toMatchObject({ condition: 'connected', severity: 'healthy' });
    expect(shouldNotify(reading)).toBe(false);
  });

  it('resolves a stale projection to stale even when the transport claims connected', () => {
    // The disagreement this source exists to remove: the chip read `connectionHealth` alone
    // and showed a green "Connected" while the banner, which also saw `isStale`, warned the
    // view could not be trusted.
    const reading = resolveConnectionState({
      isLiveMode: true,
      health: ConnectionHealthState.CONNECTED,
      isStale: true,
    });
    expect(reading).toMatchObject({ condition: 'stale', severity: 'fault' });
    expect(shouldNotify(reading)).toBe(true);
  });

  it('carries every live health through as its own condition', () => {
    for (const health of LIVE_HEALTHS) {
      expect(resolveConnectionState({ isLiveMode: true, health }).condition).toBe(health);
    }
  });

  it('treats an unrecognized or absent health as stale rather than connected', () => {
    // Claiming a healthy link nobody confirmed is the one failure an operator cannot detect.
    expect(resolveConnectionState({ isLiveMode: true, health: 'teleporting' }).condition).toBe(
      'stale',
    );
    expect(resolveConnectionState({ isLiveMode: true }).condition).toBe('stale');
  });

  it('folds the polled fixture status into the same vocabulary', () => {
    expect(
      resolveConnectionState({ isLiveMode: false, connectionStatus: 'offline' }),
    ).toMatchObject({ condition: 'disconnected', severity: 'fault' });
    expect(
      resolveConnectionState({ isLiveMode: false, connectionStatus: 'reconnecting' }),
    ).toMatchObject({ condition: 'reconnecting', severity: 'fault' });
    expect(
      resolveConnectionState({ isLiveMode: false, connectionStatus: 'connected' }),
    ).toMatchObject({ condition: 'connected', severity: 'healthy' });
  });

  it('ignores a live-mode staleness flag outside live mode', () => {
    // A fixture-backed view has no cursor to be behind.
    expect(
      resolveConnectionState({ isLiveMode: false, connectionStatus: 'connected', isStale: true })
        .isStale,
    ).toBe(false);
  });
});

describe('shouldNotify', () => {
  it('mutes informational delivery narration once the run is terminal', () => {
    // A finished run has nothing left to deliver, and nothing left to clear the notice
    // either — it would sit on screen forever.
    for (const health of [
      ConnectionHealthState.CATCHING_UP,
      ConnectionHealthState.SIMULATOR_PAUSED,
      ConnectionHealthState.LOCALLY_PAUSED,
    ]) {
      expect(
        shouldNotify(resolveConnectionState({ isLiveMode: true, health, runStatus: 'stopped' })),
      ).toBe(false);
      expect(shouldNotify(resolveConnectionState({ isLiveMode: true, health }))).toBe(true);
    }
  });

  it('keeps genuine faults on a terminal run', () => {
    for (const health of [
      ConnectionHealthState.DISCONNECTED,
      ConnectionHealthState.RECONNECTING,
      ConnectionHealthState.GAP,
      ConnectionHealthState.SNAPSHOT_RESYNC,
      ConnectionHealthState.STALE,
    ]) {
      expect(
        shouldNotify(resolveConnectionState({ isLiveMode: true, health, runStatus: 'completed' })),
      ).toBe(true);
    }
  });

  it('marks a run terminal only for statuses that actually end it', () => {
    expect(resolveConnectionState({ isLiveMode: true, runStatus: 'running' }).terminal).toBe(false);
    expect(resolveConnectionState({ isLiveMode: true, runStatus: 'paused' }).terminal).toBe(false);
    expect(resolveConnectionState({ isLiveMode: true, runStatus: 'stopped' }).terminal).toBe(true);
  });
});

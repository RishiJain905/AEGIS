import { describe, expect, it } from 'vitest';

import { classifyActivity } from './use-run-activity';

function tick(seconds: number, eventType: string) {
  const base = Date.UTC(2026, 0, 1, 0, 0, 0);
  return {
    eventType,
    sequence: seconds,
    timestamp: new Date(base + seconds * 1000).toISOString(),
  };
}

describe('classifyActivity', () => {
  it('reads an empty run as quiet', () => {
    const reading = classifyActivity([]);
    expect(reading.level).toBe('quiet');
    expect(reading.count).toBe(0);
    expect(reading.lastSimTime).toBeNull();
    expect(reading.buckets).toHaveLength(12);
  });

  it('stays quiet when only background telemetry is flowing', () => {
    const reading = classifyActivity([
      tick(10, 'telemetry.api.request'),
      tick(20, 'telemetry.api.request'),
      tick(30, 'telemetry.api.request'),
    ]);
    expect(reading.level).toBe('quiet');
    expect(reading.count).toBe(3);
  });

  it('reads a burst of failures and alerts as elevated', () => {
    const reading = classifyActivity([
      tick(10, 'telemetry.authentication.failed'),
      tick(20, 'alert.created'),
    ]);
    expect(reading.level).toBe('elevated');
  });

  it('reads status changes and a reveal as active', () => {
    const reading = classifyActivity([
      tick(10, 'alert.created'),
      tick(20, 'sim.asset.status_changed'),
      tick(30, 'sim.asset.status_changed'),
      tick(40, 'sim.hidden_condition.revealed'),
    ]);
    expect(reading.level).toBe('active');
    expect(reading.lastSimTime).toBe('2026-01-01T00:00:40.000Z');
  });

  it('ignores platform chatter so agent polling cannot make an idle run look busy', () => {
    const reading = classifyActivity([
      tick(10, 'agent.task.started'),
      tick(15, 'agent.task.completed'),
      tick(20, 'risk.projection.updated'),
      tick(25, 'report.version.created'),
    ]);
    expect(reading.level).toBe('quiet');
    expect(reading.count).toBe(0);
  });

  it('drops events that fall outside the trailing window', () => {
    const reading = classifyActivity(
      [
        tick(0, 'sim.asset.status_changed'),
        tick(5, 'sim.asset.status_changed'),
        tick(300, 'telemetry.api.request'),
      ],
      { windowSeconds: 90 },
    );
    expect(reading.count).toBe(1);
    expect(reading.level).toBe('quiet');
  });

  it('measures the window from the newest event, so a paused run holds its reading', () => {
    const paused = classifyActivity([
      tick(1000, 'alert.created'),
      tick(1010, 'sim.asset.status_changed'),
      tick(1020, 'sim.asset.status_changed'),
      tick(1030, 'alert.created'),
      tick(1040, 'alert.created'),
    ]);
    expect(paused.level).toBe('active');
  });
});

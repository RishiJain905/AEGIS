import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { ConnectionHealthState } from '@aegis/contracts-ts';

import {
  RunStatusRail,
  describeLink,
  describePosture,
  describeReport,
  describeSim,
} from './run-status-rail';

afterEach(() => {
  cleanup();
});

describe('describeLink', () => {
  it('reports a healthy link while the simulator is paused — the pause is not a link fact', () => {
    const reading = describeLink({
      isLiveMode: true,
      health: ConnectionHealthState.SIMULATOR_PAUSED,
    });
    expect(reading.label).toBe('Connected');
    expect(reading.tone).toBe('ok');
  });

  it('reports a held link when the operator paused updates locally', () => {
    const reading = describeLink({
      isLiveMode: true,
      health: ConnectionHealthState.LOCALLY_PAUSED,
    });
    expect(reading.label).toBe('Held');
    expect(reading.tone).toBe('held');
  });

  it('maps transient recovery states to a pulsing reading', () => {
    for (const health of [
      ConnectionHealthState.RECONNECTING,
      ConnectionHealthState.CATCHING_UP,
      ConnectionHealthState.SNAPSHOT_RESYNC,
      ConnectionHealthState.GAP,
    ]) {
      expect(describeLink({ isLiveMode: true, health }).pulse).toBe(true);
    }
  });

  it('falls back to the polled connection status outside live mode', () => {
    expect(describeLink({ isLiveMode: false, connectionStatus: 'offline' }).label).toBe('Offline');
    expect(describeLink({ isLiveMode: false, connectionStatus: 'connected' }).label).toBe(
      'Connected',
    );
  });
});

describe('describeSim', () => {
  it('distinguishes moving, frozen and terminal time', () => {
    expect(describeSim('running')).toMatchObject({ label: 'Running', terminal: false });
    expect(describeSim('paused')).toMatchObject({ label: 'Paused', terminal: false });
    expect(describeSim('completed')).toMatchObject({ label: 'Complete', terminal: true });
    expect(describeSim('stopped')).toMatchObject({ label: 'Stopped', terminal: true });
  });

  it('says commands still execute while paused', () => {
    expect(describeSim('paused').detail).toMatch(/frozen timeline/i);
  });

  it('explains the terminal reason from the resolved verdict', () => {
    // P3 "Silent Relay horizon is opaque": the 00:06:15 boundary is the attacker's
    // exfiltration, not a premature stop.
    const reading = describeSim('stopped', {
      outcome: 'loss_exfiltration',
      reason: 'exfiltration_completed',
      resolvedSimTime: '2026-01-01T00:06:15.000Z',
    });
    expect(reading.terminal).toBe(true);
    expect(reading.detail).toMatch(/exfiltrated data at 00:06:15/i);
    expect(reading.detail).toMatch(/read-only/i);
  });

  it('keeps the generic terminal copy when no verdict has landed', () => {
    expect(describeSim('stopped', null).detail).toMatch(/was stopped/i);
    expect(describeSim('completed', undefined).detail).toMatch(/ran to completion/i);
  });
});

describe('describePosture', () => {
  it('is critical the moment any disclosed asset is compromised', () => {
    const reading = describePosture([
      { status: 'normal' },
      { status: 'suspicious' },
      { status: 'compromised' },
    ]);
    expect(reading.posture).toBe('critical');
  });

  it('is suspicious for anomalous, investigated or contained assets', () => {
    for (const status of ['suspicious', 'under_investigation', 'contained']) {
      expect(describePosture([{ status: 'normal' }, { status }]).posture).toBe('suspicious');
    }
  });

  it('is normal for a clean or unknown estate', () => {
    expect(describePosture([{ status: 'normal' }]).posture).toBe('normal');
    expect(describePosture(undefined).posture).toBe('normal');
  });
});

describe('describeReport', () => {
  it('stays quiet while the engagement is open', () => {
    expect(describeReport({ runStatus: 'running', reportAvailable: false }).label).toBe('Underway');
  });

  it('separates "ended, report pending" from "report ready"', () => {
    expect(describeReport({ runStatus: 'stopped', reportAvailable: false }).label).toBe(
      'Debrief pending',
    );
    const ready = describeReport({ runStatus: 'completed', reportAvailable: true });
    expect(ready.label).toBe('Report ready');
    expect(ready.ready).toBe(true);
  });
});

describe('RunStatusRail', () => {
  it('renders all four instruments with their separate facts', () => {
    render(
      <RunStatusRail
        isLiveMode
        connectionHealth={ConnectionHealthState.CONNECTED}
        runStatus="paused"
        nodes={[{ status: 'suspicious' }]}
      />,
    );
    // BUG-011 regression: a paused sim must not contradict a healthy link.
    expect(screen.getByTestId('connection-status-badge')).toHaveTextContent('Connected');
    expect(screen.getByTestId('run-status')).toHaveTextContent('Paused');
    expect(screen.getByTestId('threat-posture')).toHaveTextContent('Suspicious');
    expect(screen.getByTestId('run-outcome')).toHaveTextContent('Underway');
  });

  it('hides the run-scoped instruments when there is no run to speak about', () => {
    render(<RunStatusRail isLiveMode={false} connectionStatus="connected" hasRun={false} />);
    expect(screen.getByTestId('connection-status-badge')).toHaveTextContent('Connected');
    // No placeholder facts: a rail with no run says nothing about SIM, posture, or report.
    expect(screen.queryByTestId('run-status')).not.toBeInTheDocument();
    expect(screen.queryByTestId('threat-posture')).not.toBeInTheDocument();
    expect(screen.queryByTestId('run-outcome')).not.toBeInTheDocument();
  });

  it('gives the terminal state visible precedence and lights the report chip', () => {
    render(
      <RunStatusRail
        isLiveMode
        connectionHealth={ConnectionHealthState.DISCONNECTED}
        runStatus="completed"
        nodes={[{ status: 'compromised' }]}
        reportAvailable
      />,
    );
    expect(screen.getByTestId('run-status')).toHaveTextContent('Complete');
    expect(screen.getByTestId('run-outcome')).toHaveTextContent('Report ready');
    // A dead link on an ended run is not an alarm; the instrument demotes to muted.
    expect(screen.getByTestId('connection-status-badge')).toHaveAttribute(
      'title',
      expect.stringContaining('ended'),
    );
  });
});

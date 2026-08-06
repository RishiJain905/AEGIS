import { ConnectionHealthState, type ConnectionHealthStateValue } from '@aegis/contracts-ts';

import { isRunTerminal } from '@/lib/run-status';

/**
 * The single answer to "what is the state of event delivery to this screen".
 *
 * Two surfaces narrate that state — the status strip's LINK chip and the connection banner —
 * and each used to derive it independently from a slightly different set of inputs. The chip
 * saw `connectionHealth` and the polled fixture status; the banner saw those *plus* the
 * reducer's `isStale` flag and the run's lifecycle status. So a live run whose transport
 * reported `connected` while the reducer still flagged the projection as stale showed a green
 * "Connected" chip directly above a warning banner saying "Stale state — recover before
 * trusting the live view". Both were reading their own inputs correctly; there was simply no
 * single state for them to disagree about.
 *
 * There is now. This resolves every input into one `condition` plus the two modifiers that
 * change how it should be presented, and both surfaces render from that. Copy stays with each
 * surface — the chip speaks in one-word instrument readings ("Syncing") and the banner in
 * sentences ("Applying historical events before resuming live delivery") — but neither picks
 * its own condition, so they cannot describe different ones.
 *
 * Connection state only. Simulation lifecycle (SIM), estate posture (POSTURE) and report
 * readiness (REPORT) are other instruments' facts; `runStatus` enters here solely to mute
 * delivery narration on a run that has no delivery left.
 */

/** The polled connection status served outside live mode (fixture-backed views). */
export type PolledConnectionStatus = string;

/**
 * How much the operator needs to care.
 *
 * - `healthy` — nothing to say; the banner stays silent.
 * - `informational` — a normal phase of delivery that resolves itself.
 * - `fault` — delivery is interrupted; the banner offers a manual retry.
 */
export type ConnectionSeverity = 'healthy' | 'informational' | 'fault';

export interface ConnectionReading {
  /**
   * The normalized condition, drawn from the `ConnectionHealthState` vocabulary. Outside
   * live mode the polled status is folded into the same vocabulary so downstream surfaces
   * only ever switch on one set of values.
   */
  condition: ConnectionHealthStateValue;
  severity: ConnectionSeverity;
  /** True when the projection is behind the run, whatever the transport claims. */
  isStale: boolean;
  /** True once the run is terminal: there is no delivery left to narrate. */
  terminal: boolean;
  /** Live transport vs polled fixture status. Only the copy register depends on it. */
  isLiveMode: boolean;
}

export interface ConnectionStateInput {
  isLiveMode: boolean;
  /** The live transport's health, when in live mode. */
  health?: string;
  /** The reducer's own staleness flag. */
  isStale?: boolean;
  /** The polled status used outside live mode. */
  connectionStatus?: PolledConnectionStatus;
  /** The run's lifecycle status, when known. */
  runStatus?: string;
}

const SEVERITY_BY_CONDITION: Record<ConnectionHealthStateValue, ConnectionSeverity> = {
  [ConnectionHealthState.CONNECTED]: 'healthy',
  // A paused simulator is a healthy *link* — the pause itself is the SIM instrument's fact —
  // but it still explains why the board stopped moving, so the banner may say so once.
  [ConnectionHealthState.SIMULATOR_PAUSED]: 'informational',
  [ConnectionHealthState.LOCALLY_PAUSED]: 'informational',
  [ConnectionHealthState.CATCHING_UP]: 'informational',
  [ConnectionHealthState.RECONNECTING]: 'fault',
  [ConnectionHealthState.SNAPSHOT_RESYNC]: 'fault',
  [ConnectionHealthState.GAP]: 'fault',
  [ConnectionHealthState.DISCONNECTED]: 'fault',
  [ConnectionHealthState.STALE]: 'fault',
};

function isKnownCondition(value: string): value is ConnectionHealthStateValue {
  return value in SEVERITY_BY_CONDITION;
}

/** Fold the polled fixture status into the same vocabulary the live transport uses. */
function conditionFromPolledStatus(status: string | undefined): ConnectionHealthStateValue {
  if (status === 'offline') {
    return ConnectionHealthState.DISCONNECTED;
  }
  if (status === 'reconnecting') {
    return ConnectionHealthState.RECONNECTING;
  }
  return ConnectionHealthState.CONNECTED;
}

export function resolveConnectionState(input: ConnectionStateInput): ConnectionReading {
  const terminal = isRunTerminal(input.runStatus);
  const isStale = input.isStale === true;

  if (!input.isLiveMode) {
    const condition = conditionFromPolledStatus(input.connectionStatus);
    return {
      condition,
      severity: SEVERITY_BY_CONDITION[condition],
      isStale: false,
      terminal,
      isLiveMode: false,
    };
  }

  let condition: ConnectionHealthStateValue;
  if (input.health === undefined) {
    // Live mode with no health reported yet: the transport has not spoken. Treat it as
    // stale rather than connected — claiming a healthy link nobody has confirmed is the one
    // failure mode an operator cannot detect.
    condition = ConnectionHealthState.STALE;
  } else if (!isKnownCondition(input.health)) {
    condition = ConnectionHealthState.STALE;
  } else if (input.health === ConnectionHealthState.CONNECTED && isStale) {
    // Connected but the reducer still flags the projection as behind. The staleness is the
    // load-bearing fact; reporting "connected" here is what let the chip contradict the
    // banner.
    condition = ConnectionHealthState.STALE;
  } else {
    condition = input.health;
  }

  return {
    condition,
    severity: SEVERITY_BY_CONDITION[condition],
    isStale,
    terminal,
    isLiveMode: true,
  };
}

/**
 * Whether the banner should interrupt for this reading.
 *
 * A finished run has nothing left to deliver: the informational conditions describe a
 * pipeline that no longer exists, and with no future event to clear them they would sit on
 * screen forever. Genuine faults keep their banner even on an ended run.
 */
export function shouldNotify(reading: ConnectionReading): boolean {
  if (reading.severity === 'healthy') {
    return false;
  }
  return !(reading.terminal && reading.severity === 'informational');
}

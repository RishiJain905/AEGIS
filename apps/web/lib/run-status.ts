/**
 * One answer to "is this run over", shared by every surface that changes behaviour when it is.
 *
 * The predicate lived inside the tutorial feature while the command deck and the command bar
 * each carried their own inline `status === 'stopped' || status === 'completed'`. That drift
 * is how the workspace ended up showing "RUN ENDED — commands can no longer execute" directly
 * above a row of enabled action buttons: two surfaces, two definitions of ended, one of them
 * missing. It sits in `lib/` rather than in a feature so any feature may depend on it without
 * depending on another feature.
 */

/** Run statuses past which nothing more will happen. `failed`/`aborted` are defensive. */
export const TERMINAL_RUN_STATUSES: ReadonlySet<string> = new Set([
  'completed',
  'stopped',
  'failed',
  'aborted',
]);

export function isRunTerminal(status: string | null | undefined): boolean {
  return status != null && TERMINAL_RUN_STATUSES.has(status);
}

/** `2026-01-01T00:02:30.000Z` -> `00:02:30`. Falls back to the raw value. */
export function simClock(timestamp: string | null | undefined): string {
  if (!timestamp) {
    return '—';
  }
  return /(\d{2}:\d{2}:\d{2})/.exec(timestamp)?.[1] ?? timestamp;
}

export interface RunOutcomeReading {
  /** Short label for the SIM instrument, e.g. "Exfiltration". */
  label: string;
  /** One-sentence explanation of why the run ended, for the ribbon and tooltip. */
  detail: string;
}

/**
 * The run's resolved verdict, in operator copy. `sim.run.outcome_resolved` announces the
 * verdict while the run is still `running`; the ticker STOPs right after, so a terminal
 * run's SIM instrument reads both the status and this reading to explain *why* it ended —
 * the P3 "Silent Relay horizon is opaque" fix: runs that end at 00:06:15 because the
 * attacker exfiltrated must not read as a premature stop.
 *
 * `unresolved`/`horizon_elapsed` is deliberately neutral: a manual stop also resolves as
 * UNRESOLVED (the runtime evaluates the outcome on stop), so "reached its horizon" would
 * lie about an operator-ended run.
 */
export function describeRunOutcome(
  outcome: { outcome: string; reason: string; resolvedSimTime: string } | null | undefined,
): RunOutcomeReading | null {
  if (outcome === null || outcome === undefined) {
    return null;
  }
  switch (outcome.reason) {
    case 'exfiltration_completed':
      return {
        label: 'Exfiltration',
        detail: `The attacker exfiltrated data at ${simClock(outcome.resolvedSimTime)} before containment.`,
      };
    case 'over_containment_cost':
      return {
        label: 'Over-containment',
        detail: 'Containment crossed the scenario cost fail-threshold.',
      };
    case 'critical_services_crippled':
      return {
        label: 'Critical services crippled',
        detail: 'Critical services the attacker never touched were taken offline.',
      };
    case 'all_campaigns_neutralized':
      return outcome.outcome === 'costly_win'
        ? {
            label: 'Costly win',
            detail:
              'Every campaign was neutralized, but containment crossed the warning threshold.',
          }
        : {
            label: 'Win',
            detail: 'Every attacker campaign was neutralized.',
          };
    case 'horizon_elapsed':
      return {
        label: 'Horizon reached',
        detail: 'The run ended with the attacker still active.',
      };
    default:
      return {
        label: outcome.outcome,
        detail: `The run resolved as ${outcome.outcome}.`,
      };
  }
}

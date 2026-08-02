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

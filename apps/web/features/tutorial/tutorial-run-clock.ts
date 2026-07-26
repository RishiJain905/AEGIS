/**
 * The run clock, and the walkthrough's one claim on it.
 *
 * A training run finalizes on its own once its virtual clock passes the server's horizon —
 * about eleven minutes of wall clock. The walkthrough is forty-two beats across ten chapters
 * and an operator reading it properly is nowhere near done by then, so the run used to die
 * under them mid-chapter: the hands-on beats became impossible and their objectives sat
 * pending forever with nothing on screen explaining why.
 *
 * The fix is a single, deliberate intervention. Near the end of the horizon, if the
 * walkthrough still needs the world moving, the overlay presses **Pause sim** once and says so
 * in its own voice. The run sits held instead of ending, and Resume sim / Step stay exactly
 * where chapter one taught them. It happens at most once per walkthrough and is persisted, so
 * a reload does not re-trigger it and an operator who resumes is never fought.
 *
 * Everything here is pure — no React, no fetch, no browser APIs — so each rule below is
 * directly unit-testable, and the copy lives beside the state that decides to show it.
 *
 * Why the copy is here rather than in `tutorial-content.ts`: these strings are not beats. They
 * are system notices about the run's lifecycle that can attach to *any* beat, and reading them
 * next to the predicate that raises them is what keeps the two honest.
 */

import type {
  ResolvedBeat,
  TutorialBeat,
  TutorialEvidenceKey,
  TutorialProgress,
} from './tutorial-contract';

// ---------------------------------------------------------------------------------------
// Server facts, duplicated on purpose
// ---------------------------------------------------------------------------------------

/**
 * How much virtual time a run gets before the tick engine stops it.
 *
 * The real value is server configuration: `AEGIS_SIM_MAX_SIM_SECONDS`
 * (`packages/contracts-python/src/aegis_contracts/settings.py`, defaulted in `.env.example`
 * and `docker-compose.yml`), enforced in `apps/api/src/aegis_api/runs/tick_engine.py`. It is
 * not exposed on `GET /api/v1/runs/{id}` or anywhere else the browser can read, so the only
 * way for the client to know the run is running out of time is to carry the default here.
 *
 * A deployment that raises the horizon makes this a *conservative* number: the hold fires
 * earlier than it needed to, which costs the operator one Resume sim and nothing else. A
 * deployment that lowers it below the hold point loses the hold and falls back to the
 * run-ended handling. Both degrade to something honest, which is why a duplicated constant is
 * acceptable and a guess derived from wall clock would not be.
 */
export const SIM_HORIZON_SECONDS = 1500;

/**
 * Where a run's virtual clock starts.
 *
 * Every run created through the API takes the engine's default epoch — see
 * `packages/simulation-domain/src/aegis_simulation_domain/engine.py` (`create_runtime`), which
 * `services/simulation`'s run application service never overrides. The training scenario's own
 * scheduled events are authored against the same instant. The run's `simTime` is absolute, so
 * this is what turns it into "seconds of virtual time elapsed".
 */
export const SIM_INITIAL_TIME_ISO = '2026-01-01T00:00:00.000Z';

const SIM_INITIAL_TIME_MS = Date.parse(SIM_INITIAL_TIME_ISO);

/**
 * How far into the horizon the run is allowed to get before the walkthrough holds it.
 *
 * The training scenario's whole scripted narrative has fired by 00:07:00 of virtual time, so
 * holding at 80% leaves every chapter its evidence — the alerts, the incident, BASTION's
 * proposal are all long since produced — while still leaving a comfortable margin before the
 * engine would stop the run. Pausing any earlier would starve the middle chapters, which is
 * the failure this whole module exists to avoid.
 */
export const HOLD_AT_FRACTION_OF_HORIZON = 0.8;

/** Elapsed virtual seconds at which the hold fires. */
export const HOLD_AT_ELAPSED_SIM_SECONDS = Math.round(
  SIM_HORIZON_SECONDS * HOLD_AT_FRACTION_OF_HORIZON,
);

/** The horizon in whole minutes, for copy. Derived so the prose cannot drift from the rule. */
export const SIM_HORIZON_MINUTES = Math.round(SIM_HORIZON_SECONDS / 60);

/**
 * Elapsed virtual time we are willing to believe. A run whose `simTime` sits a day past the
 * epoch is a scenario with its own initial clock, not a run twenty minutes from the horizon —
 * and the honest answer there is "unknown", never "hold it now".
 */
const MAX_PLAUSIBLE_ELAPSED_SIM_SECONDS = 86_400;

/** Run statuses past which nothing more will happen. `failed`/`aborted` are defensive. */
export const TERMINAL_RUN_STATUSES: ReadonlySet<string> = new Set([
  'completed',
  'stopped',
  'failed',
  'aborted',
]);

/** The one status in which the virtual clock is actually advancing. */
const ADVANCING_RUN_STATUS = 'running';

/** The one status the hold itself produces. */
const HELD_RUN_STATUS = 'paused';

export function isRunTerminal(status: string | null | undefined): boolean {
  return status != null && TERMINAL_RUN_STATUSES.has(status);
}

/**
 * Objectives that only the simulation can satisfy, and that a finished run therefore strands.
 *
 * Deliberately narrow. Selecting an asset, opening View options or opening an incident are
 * pure cockpit interactions and still work perfectly on a stopped run; operator commands are
 * not gated on run status either. What a terminal run really takes away is the arrival of
 * *new* world state — the clock advancing, a first alert being raised, BASTION producing a
 * containment proposal. Claiming more than that would be telling the operator something false.
 */
export const SIMULATION_DEPENDENT_EVIDENCE: ReadonlySet<TutorialEvidenceKey> =
  new Set<TutorialEvidenceKey>(['telemetryFlowing', 'alertRaised', 'proposalRaised']);

// ---------------------------------------------------------------------------------------
// Reading the clock
// ---------------------------------------------------------------------------------------

/**
 * Virtual seconds a run has burned, or `null` when that cannot be established.
 *
 * `null` is the safe answer and every caller treats it as "do nothing": an unparseable
 * timestamp, a clock behind the epoch, or an implausible distance from it all mean this module
 * does not understand the run in front of it, and a walkthrough that does not understand a run
 * has no business pausing it.
 */
export function elapsedSimSeconds(simTime: string | null | undefined): number | null {
  if (!simTime) {
    return null;
  }
  const parsed = Date.parse(simTime);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  const elapsed = (parsed - SIM_INITIAL_TIME_MS) / 1000;
  if (elapsed < 0 || elapsed > MAX_PLAUSIBLE_ELAPSED_SIM_SECONDS) {
    return null;
  }
  return elapsed;
}

/**
 * Whether the walkthrough still needs the world moving.
 *
 * The release point is the beat that *wants* the run to finish — chapter six's "Play it out",
 * found by its objective rather than by index so content edits cannot silently move it. Once
 * the operator has reached it, a run reaching its horizon is the payoff rather than a loss, and
 * the tour chapters after it read fine against a finished run. Before it, every remaining
 * hands-on beat depends on a live run.
 *
 * Keyed on `reached`, which is monotonic, so stepping back to re-read something never re-arms
 * the hold.
 */
export function walkthroughNeedsLiveRun(
  progress: TutorialProgress,
  beats: readonly ResolvedBeat[],
): boolean {
  if (beats.length === 0) {
    return false;
  }
  const release = beats.find((candidate) => candidate.beat.objective?.evidence === 'runComplete');
  if (!release) {
    // No beat asks for a finished run: the walkthrough needs the run until it is over.
    return progress.reached < beats.length - 1;
  }
  return progress.reached < release.index;
}

// ---------------------------------------------------------------------------------------
// The hold decision
// ---------------------------------------------------------------------------------------

export interface RunClockHoldInput {
  /**
   * Master switch. True only for a confirmed Synthetic Training run whose walkthrough is armed
   * and not dismissed. Everything below is inert for Operation Silent Relay and every other
   * run — an operator's live operation is never paused by this.
   */
  walkthroughActive: boolean;
  /** Whether the walkthrough still needs the run advancing (`walkthroughNeedsLiveRun`). */
  needsLiveRun: boolean;
  /** Whether this walkthrough has already spent its one hold. */
  clockHeld: boolean;
  /** The run's lifecycle status, or `null` while the run detail is still loading. */
  runStatus: string | null;
  /** The run's current virtual clock as an absolute ISO-8601 instant, or `null`. */
  simTime: string | null;
}

/**
 * Whether to press Pause sim for the operator, right now.
 *
 * Every clause is a refusal; the hold is what is left when none of them fire.
 */
export function shouldHoldRunClock(input: RunClockHoldInput): boolean {
  // Not a training walkthrough, or the operator has closed it — never touch the run.
  if (!input.walkthroughActive) {
    return false;
  }
  // At most once per walkthrough. This is what stops the overlay re-pausing a run the operator
  // deliberately resumed, across reloads as well as within a session.
  if (input.clockHeld) {
    return false;
  }
  // Past the beat that wants the run to finish: ending is the payoff now, not a loss.
  if (!input.needsLiveRun) {
    return false;
  }
  // Only a run that is actually advancing can be held. `created` has not started, `paused` is
  // already where the hold would put it, and a terminal run is past saving.
  if (input.runStatus !== ADVANCING_RUN_STATUS) {
    return false;
  }
  const elapsed = elapsedSimSeconds(input.simTime);
  if (elapsed == null) {
    return false;
  }
  return elapsed >= HOLD_AT_ELAPSED_SIM_SECONDS;
}

export interface RunClockWatchInput {
  walkthroughActive: boolean;
  needsLiveRun: boolean;
  clockHeld: boolean;
  /** Outstanding objective keys on beats the operator has reached. */
  pendingKeys: readonly TutorialEvidenceKey[];
}

/**
 * Whether the walkthrough needs to keep an eye on the run's clock and status.
 *
 * This gates a *slow* refetch of the run detail the walkthrough already reads — it never adds
 * a second query, and it stands itself down the moment neither answer can change anything:
 * once the hold is spent and no reached objective is waiting on the simulation, run status
 * stops mattering to this module.
 */
export function shouldWatchRunClock(input: RunClockWatchInput): boolean {
  if (!input.walkthroughActive) {
    return false;
  }
  if (input.needsLiveRun && !input.clockHeld) {
    return true;
  }
  return input.pendingKeys.some((key) => SIMULATION_DEPENDENT_EVIDENCE.has(key));
}

/** Record that this walkthrough has spent its hold. Identity-preserving when already set. */
export function setClockHeld(progress: TutorialProgress, clockHeld: boolean): TutorialProgress {
  if (progress.clockHeld === clockHeld) {
    return progress;
  }
  return { ...progress, clockHeld };
}

// ---------------------------------------------------------------------------------------
// What the operator is told
// ---------------------------------------------------------------------------------------

/** Which run-lifecycle notice, if any, the current beat should carry. */
export type RunClockNotice = 'held' | 'ended' | null;

export const RUN_HELD_NOTICE = `Sim held. The run was closing on its ${String(
  SIM_HORIZON_MINUTES,
)}-minute horizon, so the walkthrough pressed Pause sim rather than let it finalize while you were still working. The world is frozen, not finished — nothing on this floor expires. Resume sim or Step in the control link whenever you want the clock moving again. It only does this once.`;

export const RUN_ENDED_NOTICE =
  'This run has ended. No new telemetry, alerts or proposals will arrive, so any step here that waits on the world moving can no longer complete. Everything already on the floor stays readable, and the remaining chapters tour the rest of AEGIS — those do not need a live run. For the hands-on work, use Restart training run in the operations catalogue to take it from the top.';

/** Replaces an objective's imperative once the run can no longer produce what it asks for. */
export const UNREACHABLE_OBJECTIVE_PENDING = 'The run has ended — this one can no longer be met.';

export interface RunClockNoticeInput {
  runStatus: string | null;
  /** Whether this walkthrough has spent its hold. */
  clockHeld: boolean;
  /** Outstanding objective keys on beats the operator has reached. */
  pendingKeys: readonly TutorialEvidenceKey[];
}

/**
 * The notice to attach to whatever beat is on screen.
 *
 * `ended` wins over `held`, and is raised only when a finished run has actually cost the
 * operator something: a reached objective that only the simulation could have satisfied is
 * still outstanding. On the "Play it out" beat and everywhere after it, a finished run has cost
 * nothing, so nothing is said.
 *
 * `held` shows for exactly as long as it is true — the run sits paused by our hand. The moment
 * the operator resumes, the explanation stops following them around.
 */
export function runClockNotice(input: RunClockNoticeInput): RunClockNotice {
  if (
    isRunTerminal(input.runStatus) &&
    input.pendingKeys.some((key) => SIMULATION_DEPENDENT_EVIDENCE.has(key))
  ) {
    return 'ended';
  }
  if (input.clockHeld && input.runStatus === HELD_RUN_STATUS) {
    return 'held';
  }
  return null;
}

/**
 * Fold a notice into a beat.
 *
 * The overlay renders beats; it has no notion of run lifecycle and does not need one. Adding
 * the paragraph here means the notice inherits the card's own layout, spotlight and screen
 * reader announcement for free, and the overlay stays a pure function of the beat it is given.
 *
 * Identity is preserved when there is nothing to say, so the overlay's anchor measurement does
 * not re-run on every render.
 */
export function applyRunClockNotice(beat: TutorialBeat, notice: RunClockNotice): TutorialBeat {
  if (notice == null) {
    return beat;
  }
  if (notice === 'held') {
    return { ...beat, body: [...beat.body, RUN_HELD_NOTICE] };
  }
  const objective = beat.objective;
  const stranded = objective != null && SIMULATION_DEPENDENT_EVIDENCE.has(objective.evidence);
  const body = [...beat.body, RUN_ENDED_NOTICE];
  if (!stranded) {
    return { ...beat, body };
  }
  // Only `pending` is rewritten: an objective satisfied before the run ended still reads as met.
  return { ...beat, body, objective: { ...objective, pending: UNREACHABLE_OBJECTIVE_PENDING } };
}

/** `applyRunClockNotice` for the positioned beat the overlay actually renders. */
export function withRunClockNotice(resolved: ResolvedBeat, notice: RunClockNotice): ResolvedBeat {
  const beat = applyRunClockNotice(resolved.beat, notice);
  if (beat === resolved.beat) {
    return resolved;
  }
  return { ...resolved, beat };
}

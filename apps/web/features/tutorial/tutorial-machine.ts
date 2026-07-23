/**
 * Pure state machine for the Synthetic Training guided walkthrough.
 *
 * The tutorial is driven by REAL run evidence — not timers. Each step declares the
 * observable fact that satisfies its objective; the machine derives the active step
 * from a snapshot of that evidence plus a monotonic `floor` (the furthest step ever
 * reached, persisted so a reload resumes rather than restarts).
 *
 * Two advancement modes are intentionally different:
 *  - Ambient steps (telemetry flowing, first alert, run complete) advance only when
 *    their own evidence appears, so a fresh run walks through them at the pace of the
 *    simulation instead of leaping past coaching the operator has not read yet.
 *  - User milestones (opened an incident, tasked an agent, resolved a proposal) also
 *    pull the walkthrough forward via skip-ahead, so an operator who races ahead of the
 *    script is never shown a step whose goal they have already met.
 *
 * Kept free of React and browser APIs so it can be unit-tested directly.
 */

export const TUTORIAL_STEP_IDS = [
  'welcome',
  'watch',
  'first-blood',
  'open-incident',
  'task-copilot',
  'containment',
  'endgame',
  'debrief',
] as const;

export type TutorialStepId = (typeof TUTORIAL_STEP_IDS)[number];

export const STEP_COUNT = TUTORIAL_STEP_IDS.length;
const LAST_INDEX = STEP_COUNT - 1;

/**
 * A snapshot of everything the walkthrough can observe about a live run. Every field is
 * a plain boolean so the machine stays pure and trivially testable; the React layer maps
 * TanStack query results and route state onto this shape.
 */
export interface TutorialEvidence {
  /** Operator clicked "Begin walkthrough" (manual gate on the welcome step). */
  welcomeAcknowledged: boolean;
  /** New simulation events have flowed since the operator arrived (the ops floor is live). */
  telemetryFlowing: boolean;
  /** At least one alert has been raised on the run. */
  alertRaised: boolean;
  /** The operator has opened/selected an incident. */
  incidentOpened: boolean;
  /** At least one agent task/artifact exists for the engaged incident. */
  agentTaskCreated: boolean;
  /** A response proposal has been approved or rejected. */
  containmentResolved: boolean;
  /** The run has finished (completed or stopped). */
  runComplete: boolean;
}

export const EMPTY_EVIDENCE: TutorialEvidence = {
  welcomeAcknowledged: false,
  telemetryFlowing: false,
  alertRaised: false,
  incidentOpened: false,
  agentTaskCreated: false,
  containmentResolved: false,
  runComplete: false,
};

export interface TutorialProgress {
  /** Monotonic furthest-reached step index, persisted across reloads. */
  reached: number;
  /** Whether the operator has acknowledged the welcome step. */
  welcomeAcknowledged: boolean;
  /** Whether the operator dismissed the whole walkthrough (skip / finished). */
  dismissed: boolean;
}

export const INITIAL_PROGRESS: TutorialProgress = {
  reached: 0,
  welcomeAcknowledged: false,
  dismissed: false,
};

/** Whether step `index`'s own objective evidence is present. */
function stepSatisfied(index: number, evidence: TutorialEvidence): boolean {
  switch (index) {
    case 0:
      return evidence.welcomeAcknowledged;
    case 1:
      return evidence.telemetryFlowing;
    case 2:
      return evidence.alertRaised;
    case 3:
      return evidence.incidentOpened;
    case 4:
      return evidence.agentTaskCreated;
    case 5:
      return evidence.containmentResolved;
    case 6:
      return evidence.runComplete;
    default:
      // Debrief is terminal — it never auto-completes; it is dismissed instead.
      return false;
  }
}

/** User-driven and terminal milestones that justify skipping the walkthrough forward. */
const SKIP_AHEAD_MILESTONES: ReadonlyArray<{
  index: number;
  reached: (evidence: TutorialEvidence) => boolean;
}> = [
  { index: 3, reached: (e) => e.incidentOpened },
  { index: 4, reached: (e) => e.agentTaskCreated },
  { index: 5, reached: (e) => e.containmentResolved },
  { index: 6, reached: (e) => e.runComplete },
];

function skipAheadFloor(evidence: TutorialEvidence, current: number): number {
  let floor = current;
  for (const milestone of SKIP_AHEAD_MILESTONES) {
    if (milestone.reached(evidence)) {
      floor = Math.max(floor, milestone.index + 1);
    }
  }
  return floor;
}

/**
 * Resolve the currently active step index from evidence and the persisted floor.
 *
 * The result never drops below `floor` (progress is monotonic) and never exceeds the
 * terminal debrief step.
 */
export function computeActiveStep(evidence: TutorialEvidence, floor: number): number {
  let step = Math.max(0, Math.min(floor, LAST_INDEX));

  // Welcome is a hard manual gate: hold here until acknowledged, unless the operator has
  // already raced past it into a user milestone.
  if (step === 0 && !evidence.welcomeAcknowledged) {
    return Math.min(skipAheadFloor(evidence, 0), LAST_INDEX);
  }
  if (step === 0) {
    step = 1;
  }

  // Advance through any steps whose own evidence is already present (an already-met goal
  // is never shown), then honour skip-ahead milestones so we never trail the operator.
  while (step < LAST_INDEX && stepSatisfied(step, evidence)) {
    step += 1;
  }
  step = Math.max(step, skipAheadFloor(evidence, step));

  return Math.min(step, LAST_INDEX);
}

/** Whether `index` is the terminal debrief step. */
export function isDebriefStep(index: number): boolean {
  return index >= LAST_INDEX;
}

/**
 * Fold a fresh active-step computation into persisted progress, keeping `reached`
 * monotonic. Returns the same object identity when nothing changed so callers can skip
 * redundant writes/renders.
 */
export function advanceProgress(
  progress: TutorialProgress,
  activeStep: number,
): TutorialProgress {
  if (activeStep <= progress.reached) {
    return progress;
  }
  return { ...progress, reached: activeStep };
}

/**
 * Shared contract for the guided walkthrough.
 *
 * The walkthrough is a sequence of *chapters*, each holding an ordered list of *beats*.
 * A beat is one coach mark. Two kinds:
 *
 *  - `learn` — points at a panel and explains what it shows. Advances when the operator
 *    clicks Next. Never depends on simulation state, so an operator can read the whole
 *    cockpit tour at their own pace while telemetry builds in the background.
 *  - `do` — asks the operator to actually perform something, and names the observable
 *    evidence that proves they did. Performing the real action checks the objective off and
 *    pulls the walkthrough forward; whether an *unmet* objective blocks `Next` depends on its
 *    declared {@link TutorialObjectiveRequirement}.
 *
 * Objectives are declaratively gated, not uniformly soft. `required` objectives — ones under
 * the operator's own control, or ones the deterministic training scenario reliably produces
 * in time — block `Next` until satisfied. `skippable` objectives, which depend on run state
 * that may never materialise this playthrough (an incident that never correlates, a model
 * that never replies), also block `Next`, but the operator can explicitly "Skip objective" to
 * get past one, and the skip is recorded rather than hidden. `optional` objectives never
 * block at all. This is what stops the walkthrough either stranding an operator on state the
 * run cannot produce, or silently letting them past a beat they never actually completed.
 *
 * This module is pure data and types — no React, no browser APIs — so the machine, the
 * overlay and the content can be built and tested independently of one another.
 */

/**
 * Everything the walkthrough can observe about a live run. Every field is a plain boolean
 * so the machine stays pure and trivially testable; the React layer maps TanStack query
 * results, route state and the workspace UI store onto this shape.
 */
export interface TutorialEvidence {
  /** Operator acknowledged the opening beat. */
  welcomeAcknowledged: boolean;
  /** New simulation time has been observed since the operator arrived. */
  telemetryFlowing: boolean;
  /** The operator has selected any asset on the graph. */
  assetSelected: boolean;
  /** The operator has opened the graph's view-options panel. */
  graphOptionsOpened: boolean;
  /** At least one alert has been raised on the run. */
  alertRaised: boolean;
  /**
   * An alert has been raised *and* the operator has opened its Explanation disclosure — see
   * BUG-005. `alertRaised` alone proves the alert is visible, not read; this is the stricter
   * evidence the "read the explanation" objective actually needs.
   */
  alertExplanationOpened: boolean;
  /** The operator has opened or selected an incident. */
  incidentOpened: boolean;
  /** The operator has executed any operator command against an asset. */
  operatorActionExecuted: boolean;
  /** The operator has executed a Class 2+ command through the consequences dialog. */
  containmentActionExecuted: boolean;
  /** At least one agent task/artifact exists for the engaged incident. */
  agentTaskCreated: boolean;
  /** An agent has replied with an artifact the operator can read. */
  agentReplyReceived: boolean;
  /** A response proposal exists on the engaged incident. */
  proposalRaised: boolean;
  /** A proposal has been approved or rejected. */
  containmentResolved: boolean;
  /** The run has finished (completed or stopped). */
  runComplete: boolean;
  /** The after-action report is available. */
  reportReady: boolean;
}

export type TutorialEvidenceKey = keyof TutorialEvidence;

export const EMPTY_EVIDENCE: TutorialEvidence = {
  welcomeAcknowledged: false,
  telemetryFlowing: false,
  assetSelected: false,
  graphOptionsOpened: false,
  alertRaised: false,
  alertExplanationOpened: false,
  incidentOpened: false,
  operatorActionExecuted: false,
  containmentActionExecuted: false,
  agentTaskCreated: false,
  agentReplyReceived: false,
  proposalRaised: false,
  containmentResolved: false,
  runComplete: false,
  reportReady: false,
};

export type TutorialBeatKind = 'learn' | 'do';

/**
 * How strictly an objective gates `Next`.
 *
 *  - `required` — blocks `Next` until the evidence lands. Reserved for objectives the
 *    operator can always satisfy under their own control (select a node, open a panel, send
 *    a message) or that the deterministic training scenario reliably produces in time.
 *  - `skippable` — blocks `Next` until the evidence lands *or* the operator explicitly
 *    chooses "Skip objective". Use for objectives that depend on state the run may not have
 *    produced yet (an incident that has not correlated, a proposal that needs a live model),
 *    so a genuinely stuck operator has a deliberate way through rather than a dead end.
 *  - `optional` — never blocks `Next` and carries no skip affordance; it can simply go unmet.
 */
export type TutorialObjectiveRequirement = 'required' | 'optional' | 'skippable';

/** The observable goal of a `do` beat, and the copy shown either side of satisfying it. */
export interface TutorialObjective {
  /** The evidence flag that proves the operator did the thing. */
  evidence: TutorialEvidenceKey;
  /** Imperative one-liner shown while the objective is outstanding. */
  pending: string;
  /** Confirmation shown once the evidence lands. */
  done: string;
  /**
   * When true the beat auto-advances the moment its evidence appears. Use for objectives
   * whose payoff is immediate; leave false when the operator should stay and read the
   * result of what they just did.
   */
  advanceOnSatisfied?: boolean;
  /** Declares whether this objective gates `Next`, and how — see {@link TutorialObjectiveRequirement}. */
  requirement: TutorialObjectiveRequirement;
  /**
   * Why this objective might not be satisfiable this run — shown beside the "Skip objective"
   * affordance and in the completion summary. Required on `skippable` objectives.
   */
  skipReason?: string;
}

export interface TutorialBeat {
  /** Stable, unique across the whole walkthrough. Used for progress and test hooks. */
  id: string;
  kind: TutorialBeatKind;
  title: string;
  /** Body paragraphs. Keep each to a couple of sentences; the card is narrow. */
  body: string[];
  /**
   * CSS selectors the spotlight anchors to, tried in order — the first element present in
   * the DOM wins. An empty list, or no match at runtime, renders the card centred in a
   * graceful degraded mode with the same copy and controls.
   */
  anchors: string[];
  /** What the operator is being pointed at, announced to assistive tech. */
  pointerLabel: string;
  /** Present on `do` beats; absent on `learn` beats. */
  objective?: TutorialObjective;
  /**
   * A shell surface this beat is about. The overlay uses it to offer a "take me there"
   * affordance when the operator is somewhere else; it never navigates on its own.
   */
  surface?: TutorialSurface;
  /** Optional call-to-action rendered on the card. */
  primaryAction?: 'begin' | 'launch-next';
}

/** Shell surfaces a beat can point the operator at. */
export type TutorialSurface =
  | 'run'
  | 'incidents'
  | 'after-action'
  | 'reports'
  | 'replay'
  | 'admin'
  | 'scenarios';

export interface TutorialChapter {
  /** Stable, unique. Used by the chapter menu and persisted progress. */
  id: string;
  /** Shown in the chapter menu and as the card eyebrow. */
  title: string;
  /** One line in the chapter menu explaining what the chapter covers. */
  summary: string;
  /**
   * Cockpit chapters are the deep ones; `tour` chapters are the brief passes over the rest
   * of the app. The overlay uses this only for grouping in the chapter menu.
   */
  section: 'cockpit' | 'tour';
  beats: TutorialBeat[];
}

/** A beat plus its position, which is what the overlay actually renders. */
export interface ResolvedBeat {
  beat: TutorialBeat;
  chapter: TutorialChapter;
  /** Absolute index across the flattened walkthrough. */
  index: number;
  /** 1-based position within the chapter. */
  beatNumber: number;
  /** Total beats in this chapter. */
  beatCount: number;
  /** 1-based position of the chapter. */
  chapterNumber: number;
  /** Total chapters. */
  chapterCount: number;
}

/**
 * Persisted walkthrough progress, stored per run.
 *
 * `cursor` is where the operator actually is; `reached` is the furthest beat ever visited,
 * so Back never loses the ability to return, and a reload resumes rather than restarts.
 */
export interface TutorialProgress {
  /** Schema tag so a future content change can migrate or reset stored progress. */
  version: number;
  cursor: number;
  reached: number;
  /** Beat ids whose objectives have been satisfied at least once. */
  completedBeatIds: string[];
  /**
   * Beat ids whose `skippable` objective the operator explicitly skipped via "Skip
   * objective". Distinct from `completedBeatIds` — a skipped objective was never met, and the
   * completion summary and chapter menu say so honestly rather than folding it into "done".
   */
  skippedBeatIds: string[];
  /** Operator collapsed the card to its pill. */
  minimized: boolean;
  /** Operator dismissed the walkthrough. Reopenable — this is not a one-way door. */
  dismissed: boolean;
  /**
   * The walkthrough has spent its one hold on this run's simulation clock — see
   * `tutorial-run-clock.ts`. Persisted so a reload cannot pause the run a second time, and so
   * an operator who resumes manually is never fought.
   */
  clockHeld: boolean;
}

export const TUTORIAL_PROGRESS_VERSION = 4;

export const INITIAL_PROGRESS: TutorialProgress = {
  version: TUTORIAL_PROGRESS_VERSION,
  cursor: 0,
  reached: 0,
  completedBeatIds: [],
  skippedBeatIds: [],
  minimized: false,
  dismissed: false,
  clockHeld: false,
};

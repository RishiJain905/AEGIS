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
 *    evidence that proves they did. Soft-gated: Next is always available, but performing
 *    the real action checks the objective off and pulls the walkthrough forward.
 *
 * Soft gating is deliberate. Several objectives (a first alert, an incident, a BASTION
 * proposal) can only be satisfied once the simulation produces them, which takes minutes.
 * A hard gate would strand the operator staring at a spinner; instead the objective stays
 * visible and self-completes whenever the evidence lands.
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

export const TUTORIAL_PROGRESS_VERSION = 3;

export const INITIAL_PROGRESS: TutorialProgress = {
  version: TUTORIAL_PROGRESS_VERSION,
  cursor: 0,
  reached: 0,
  completedBeatIds: [],
  minimized: false,
  dismissed: false,
  clockHeld: false,
};

/**
 * Public surface of the guided walkthrough.
 *
 * The walkthrough is a chapter/beat model: `tutorial-contract.ts` holds the shared types,
 * `tutorial-content.ts` the authored chapters, `tutorial-machine.ts` the pure transitions,
 * and the components render them. Callers outside this feature should need only
 * `TutorialController` (mounted once in the shell layout) and `armTutorial` (called by the
 * operations catalogue when a training run is launched) — importing the storage helper
 * directly, as the catalogue does, keeps the overlay/evidence graph out of that bundle.
 */

export { TutorialController } from './components/tutorial-controller';
export { CoachMarkOverlay } from './components/coach-mark-overlay';
export { ChapterMenu } from './components/chapter-menu';
export { armTutorial } from './tutorial-storage';

export {
  EMPTY_EVIDENCE,
  INITIAL_PROGRESS,
  TUTORIAL_PROGRESS_VERSION,
  type ResolvedBeat,
  type TutorialBeat,
  type TutorialBeatKind,
  type TutorialChapter,
  type TutorialEvidence,
  type TutorialEvidenceKey,
  type TutorialObjective,
  type TutorialObjectiveRequirement,
  type TutorialProgress,
  type TutorialSurface,
} from './tutorial-contract';

export { TUTORIAL_CHAPTERS, allBeats, beatById, chapterById } from './tutorial-content';

export {
  applyEvidence,
  clampProgress,
  flattenChapters,
  goBack,
  goNext,
  isObjectiveSatisfied,
  isWalkthroughComplete,
  jumpToChapter,
  objectiveAudit,
  objectiveBlockReason,
  pendingObjectiveKeys,
  resolveCurrentBeat,
  setDismissed,
  setMinimized,
  skipChapter,
  skipObjective,
  type ObjectiveAuditEntry,
} from './tutorial-machine';

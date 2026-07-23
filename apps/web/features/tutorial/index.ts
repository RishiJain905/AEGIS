export { TutorialController } from './components/tutorial-controller';
export { CoachMarkOverlay } from './components/coach-mark-overlay';
export { armTutorial } from './tutorial-storage';
export {
  computeActiveStep,
  advanceProgress,
  isDebriefStep,
  STEP_COUNT,
  TUTORIAL_STEP_IDS,
  EMPTY_EVIDENCE,
  INITIAL_PROGRESS,
  type TutorialEvidence,
  type TutorialProgress,
  type TutorialStepId,
} from './tutorial-machine';
export { TUTORIAL_STEPS, type TutorialStepContent } from './tutorial-steps';

import { describe, expect, it } from 'vitest';

import {
  EMPTY_EVIDENCE,
  INITIAL_PROGRESS,
  STEP_COUNT,
  advanceProgress,
  computeActiveStep,
  isDebriefStep,
  type TutorialEvidence,
} from './tutorial-machine';

function evidence(overrides: Partial<TutorialEvidence>): TutorialEvidence {
  return { ...EMPTY_EVIDENCE, ...overrides };
}

const WELCOME = 0;
const WATCH = 1;
const FIRST_BLOOD = 2;
const OPEN_INCIDENT = 3;
const TASK_COPILOT = 4;
const CONTAINMENT = 5;
const ENDGAME = 6;
const DEBRIEF = 7;

describe('tutorial-machine · computeActiveStep', () => {
  it('holds on the welcome step until it is acknowledged', () => {
    expect(computeActiveStep(EMPTY_EVIDENCE, 0)).toBe(WELCOME);
    expect(computeActiveStep(evidence({ telemetryFlowing: true }), 0)).toBe(WELCOME);
  });

  it('advances through the ambient steps as their own evidence arrives', () => {
    expect(computeActiveStep(evidence({ welcomeAcknowledged: true }), 0)).toBe(WATCH);
    expect(
      computeActiveStep(evidence({ welcomeAcknowledged: true, telemetryFlowing: true }), 0),
    ).toBe(FIRST_BLOOD);
    expect(
      computeActiveStep(
        evidence({ welcomeAcknowledged: true, telemetryFlowing: true, alertRaised: true }),
        0,
      ),
    ).toBe(OPEN_INCIDENT);
  });

  it('does not leap past the watch step from ambient telemetry before welcome is acknowledged', () => {
    // Telemetry and an alert are present, but the operator has not begun: they stay on
    // welcome rather than being skipped past the coaching.
    expect(computeActiveStep(evidence({ telemetryFlowing: true, alertRaised: true }), 0)).toBe(
      WELCOME,
    );
  });

  it('walks the full happy path one user milestone at a time', () => {
    const base = { welcomeAcknowledged: true, telemetryFlowing: true, alertRaised: true };
    expect(computeActiveStep(evidence({ ...base, incidentOpened: true }), 0)).toBe(TASK_COPILOT);
    expect(
      computeActiveStep(evidence({ ...base, incidentOpened: true, agentTaskCreated: true }), 0),
    ).toBe(CONTAINMENT);
    expect(
      computeActiveStep(
        evidence({
          ...base,
          incidentOpened: true,
          agentTaskCreated: true,
          containmentResolved: true,
        }),
        0,
      ),
    ).toBe(ENDGAME);
  });

  it('advances endgame to the debrief only when the run completes', () => {
    const done = evidence({
      welcomeAcknowledged: true,
      telemetryFlowing: true,
      alertRaised: true,
      incidentOpened: true,
      agentTaskCreated: true,
      containmentResolved: true,
    });
    expect(computeActiveStep(done, 0)).toBe(ENDGAME);
    expect(computeActiveStep({ ...done, runComplete: true }, 0)).toBe(DEBRIEF);
  });

  it('supports skip-ahead: a satisfied user milestone pulls the walkthrough forward', () => {
    // The operator opened an incident and tasked an agent while the overlay was still on
    // an early step; the machine jumps to the step after the furthest milestone.
    expect(computeActiveStep(evidence({ incidentOpened: true, agentTaskCreated: true }), 0)).toBe(
      CONTAINMENT,
    );
  });

  it('never regresses below the persisted floor', () => {
    // Evidence has receded (e.g. a poll returned empty) but the floor holds the step.
    expect(computeActiveStep(EMPTY_EVIDENCE, CONTAINMENT)).toBe(CONTAINMENT);
  });

  it('clamps to the terminal debrief step', () => {
    expect(computeActiveStep(evidence({ runComplete: true }), STEP_COUNT + 5)).toBe(DEBRIEF);
    expect(isDebriefStep(DEBRIEF)).toBe(true);
    expect(isDebriefStep(ENDGAME)).toBe(false);
  });
});

describe('tutorial-machine · advanceProgress', () => {
  it('raises the floor monotonically and preserves object identity when unchanged', () => {
    const raised = advanceProgress(INITIAL_PROGRESS, OPEN_INCIDENT);
    expect(raised.reached).toBe(OPEN_INCIDENT);

    const noChange = advanceProgress(raised, WATCH);
    expect(noChange).toBe(raised);

    const higher = advanceProgress(raised, ENDGAME);
    expect(higher.reached).toBe(ENDGAME);
  });
});

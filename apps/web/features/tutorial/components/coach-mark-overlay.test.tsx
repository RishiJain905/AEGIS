import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import { CoachMarkOverlay } from './coach-mark-overlay';
import { TUTORIAL_STEPS, type TutorialStepContent } from '../tutorial-steps';

function stepAt(index: number): TutorialStepContent {
  const step = TUTORIAL_STEPS[index];
  if (!step) {
    throw new Error(`No tutorial step at index ${String(index)}`);
  }
  return step;
}

const WELCOME_STEP = stepAt(0);
const FIRST_BLOOD_STEP = stepAt(2);
const DEBRIEF_STEP = stepAt(TUTORIAL_STEPS.length - 1);

function renderOverlay(step = WELCOME_STEP) {
  const handlers = {
    onBegin: vi.fn(),
    onSkipStep: vi.fn(),
    onSkipTutorial: vi.fn(),
    onLaunchNext: vi.fn(),
  };
  render(<CoachMarkOverlay step={step} {...handlers} />);
  return handlers;
}

afterEach(() => {
  cleanup();
});

describe('CoachMarkOverlay', () => {
  it('renders an accessible dialog named by the step title', () => {
    renderOverlay();
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'false');
    expect(dialog).toHaveAccessibleName(WELCOME_STEP.title);
  });

  it('announces the active step through a polite live region', () => {
    renderOverlay();
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-live', 'polite');
    expect(status).toHaveTextContent(WELCOME_STEP.title);
  });

  it('never captures pointer events on the dimming layer, keeping controls clickable', () => {
    renderOverlay();
    expect(screen.getByTestId('tutorial-overlay').className).toContain('pointer-events-none');
    expect(screen.getByTestId('tutorial-coach-mark').className).toContain('pointer-events-auto');
  });

  it('offers a begin action on the welcome step and wires the handlers', () => {
    const handlers = renderOverlay();
    fireEvent.click(screen.getByTestId('tutorial-begin'));
    expect(handlers.onBegin).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByTestId('tutorial-skip-tutorial'));
    expect(handlers.onSkipTutorial).toHaveBeenCalledTimes(1);
  });

  it('offers a per-step skip on evidence-driven steps and waits with an advance hint', () => {
    const handlers = renderOverlay(FIRST_BLOOD_STEP);
    expect(screen.getByTestId('tutorial-advance-hint')).toHaveTextContent(
      FIRST_BLOOD_STEP.advanceHint,
    );
    fireEvent.click(screen.getByTestId('tutorial-skip-step'));
    expect(handlers.onSkipStep).toHaveBeenCalledTimes(1);
  });

  it('offers the next-operation CTA on the debrief step', () => {
    const handlers = renderOverlay(DEBRIEF_STEP);
    fireEvent.click(screen.getByTestId('tutorial-launch-next'));
    expect(handlers.onLaunchNext).toHaveBeenCalledTimes(1);
  });

  it('degrades to a centred card when the anchor is absent from the DOM', () => {
    // FIRST_BLOOD_STEP anchors at inspector/alerts panels that are not mounted here.
    renderOverlay(FIRST_BLOOD_STEP);
    expect(screen.getByTestId('tutorial-coach-mark')).toBeInTheDocument();
  });

  it.each(['dark', 'light'] as const)(
    'has no detectable accessibility violations (%s theme)',
    async (theme) => {
      document.documentElement.setAttribute('data-theme', theme);
      try {
        renderOverlay();
        const results = await axe(document.body);
        expect(results.violations).toHaveLength(0);
      } finally {
        document.documentElement.removeAttribute('data-theme');
      }
    },
  );
});

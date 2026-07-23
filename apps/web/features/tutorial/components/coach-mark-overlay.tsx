'use client';

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import { Button, VisuallyHidden, cn, typographyTokens, useReducedMotion } from '@aegis/ui';

import { STEP_COUNT } from '../tutorial-machine';
import type { TutorialStepContent } from '../tutorial-steps';

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

export interface CoachMarkOverlayProps {
  step: TutorialStepContent;
  onBegin: () => void;
  onSkipStep: () => void;
  onSkipTutorial: () => void;
  onLaunchNext: () => void;
}

const CARD_GAP = 14;
const VIEWPORT_MARGIN = 16;
const SPOTLIGHT_PADDING = 8;
const RESOLVE_INTERVAL_MS = 400;

function resolveAnchor(anchors: readonly string[]): Element | null {
  if (typeof document === 'undefined') {
    return null;
  }
  for (const selector of anchors) {
    const element = document.querySelector(selector);
    if (element) {
      return element;
    }
  }
  return null;
}

function rectsDiffer(a: Rect | null, b: Rect | null): boolean {
  if (a === b) {
    return false;
  }
  if (!a || !b) {
    return true;
  }
  return (
    Math.round(a.top) !== Math.round(b.top) ||
    Math.round(a.left) !== Math.round(b.left) ||
    Math.round(a.width) !== Math.round(b.width) ||
    Math.round(a.height) !== Math.round(b.height)
  );
}

/**
 * Anchored spotlight + callout card for one walkthrough step.
 *
 * The dimming layer never captures pointer events, so every highlighted control stays
 * clickable — the operator can act on the very thing being pointed at without dismissing
 * the coach mark. When a step's anchor is absent (e.g. the copilot panel has not mounted
 * its `data-tutorial-id` hooks yet) the card renders centred in a degraded-but-usable
 * mode with the same copy and controls.
 */
export function CoachMarkOverlay({
  step,
  onBegin,
  onSkipStep,
  onSkipTutorial,
  onLaunchNext,
}: CoachMarkOverlayProps) {
  const reducedMotion = useReducedMotion();
  const [mounted, setMounted] = useState(false);
  const [anchorRect, setAnchorRect] = useState<Rect | null>(null);
  const [cardPos, setCardPos] = useState<{ top: number; left: number } | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Track the anchor element's viewport rect. A short polling interval (plus scroll/resize
  // listeners) keeps the spotlight aligned through layout shifts and picks up anchors that
  // mount after this step becomes active.
  useEffect(() => {
    if (!mounted) {
      return;
    }
    let current: Rect | null = anchorRect;
    const update = () => {
      const element = resolveAnchor(step.anchors);
      const next: Rect | null = element
        ? (() => {
            const box = element.getBoundingClientRect();
            return { top: box.top, left: box.left, width: box.width, height: box.height };
          })()
        : null;
      if (rectsDiffer(current, next)) {
        current = next;
        setAnchorRect(next);
      }
    };
    update();
    const interval = window.setInterval(update, RESOLVE_INTERVAL_MS);
    window.addEventListener('scroll', update, true);
    window.addEventListener('resize', update);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener('scroll', update, true);
      window.removeEventListener('resize', update);
    };
    // Intentionally re-armed only when the step (and thus its anchor list) changes; the
    // `anchorRect` seed is read once at setup and thereafter tracked via `current`.
  }, [mounted, step.id]);

  // Position the card relative to the anchor, clamped inside the viewport. Falls back to
  // centred when there is no anchor.
  useLayoutEffect(() => {
    if (!anchorRect) {
      setCardPos(null);
      return;
    }
    const card = cardRef.current;
    const cardWidth = card?.offsetWidth ?? 360;
    const cardHeight = card?.offsetHeight ?? 260;
    const viewportWidth = window.innerWidth || 1280;
    const viewportHeight = window.innerHeight || 800;

    let top = anchorRect.top + anchorRect.height + CARD_GAP;
    if (top + cardHeight > viewportHeight - VIEWPORT_MARGIN) {
      const above = anchorRect.top - cardHeight - CARD_GAP;
      top =
        above >= VIEWPORT_MARGIN
          ? above
          : Math.max(VIEWPORT_MARGIN, viewportHeight - cardHeight - VIEWPORT_MARGIN);
    }
    const left = Math.min(
      Math.max(anchorRect.left, VIEWPORT_MARGIN),
      Math.max(VIEWPORT_MARGIN, viewportWidth - cardWidth - VIEWPORT_MARGIN),
    );
    setCardPos({ top, left });
  }, [anchorRect, step.id]);

  // Move focus to the card heading on each step change, without trapping focus — the
  // operator must remain free to interact with the highlighted control.
  useEffect(() => {
    if (!mounted) {
      return;
    }
    const frame = window.requestAnimationFrame(() => {
      cardRef.current?.focus();
    });
    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [mounted, step.id]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onSkipTutorial();
      }
    },
    [onSkipTutorial],
  );

  if (!mounted) {
    return null;
  }

  const stepNumber = step.index + 1;
  const isCentered = anchorRect == null;
  const titleId = `tutorial-step-title-${step.id}`;
  const bodyId = `tutorial-step-body-${step.id}`;

  const dimStyle: React.CSSProperties | undefined = anchorRect
    ? {
        position: 'fixed',
        top: anchorRect.top - SPOTLIGHT_PADDING,
        left: anchorRect.left - SPOTLIGHT_PADDING,
        width: anchorRect.width + SPOTLIGHT_PADDING * 2,
        height: anchorRect.height + SPOTLIGHT_PADDING * 2,
        boxShadow: '0 0 0 9999px color-mix(in srgb, var(--aegis-surface-base) 68%, transparent)',
        borderRadius: 'var(--aegis-radius-lg)',
      }
    : undefined;

  const cardStyle: React.CSSProperties = isCentered
    ? {
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
      }
    : {
        position: 'fixed',
        top: cardPos?.top ?? VIEWPORT_MARGIN,
        left: cardPos?.left ?? VIEWPORT_MARGIN,
        transition: reducedMotion ? undefined : 'top 160ms ease, left 160ms ease',
      };

  return createPortal(
    <div
      className="pointer-events-none fixed inset-0 z-[120]"
      data-testid="tutorial-overlay"
      data-tutorial-step={step.id}
    >
      {/* Centred narrative steps get a soft full scrim; anchored steps get a spotlight. */}
      {isCentered ? (
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-[color-mix(in_srgb,var(--aegis-surface-base)_60%,transparent)] backdrop-blur-[2px]"
        />
      ) : (
        <>
          <div aria-hidden="true" style={dimStyle} />
          <div
            aria-hidden="true"
            style={{
              position: 'fixed',
              top: anchorRect.top - SPOTLIGHT_PADDING,
              left: anchorRect.left - SPOTLIGHT_PADDING,
              width: anchorRect.width + SPOTLIGHT_PADDING * 2,
              height: anchorRect.height + SPOTLIGHT_PADDING * 2,
              borderRadius: 'var(--aegis-radius-lg)',
            }}
            className={cn(
              'ring-2 ring-[var(--aegis-accent-line)] ring-offset-0',
              'shadow-[0_0_0_1px_var(--aegis-accent-strong),0_0_24px_color-mix(in_srgb,var(--aegis-accent-cyan)_40%,transparent)]',
              !reducedMotion && 'animate-pulse',
            )}
          />
        </>
      )}

      <div
        ref={cardRef}
        role="dialog"
        aria-modal="false"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        style={cardStyle}
        className={cn(
          'pointer-events-auto w-[min(92vw,23rem)] overflow-hidden rounded-[var(--aegis-radius-xl)]',
          'border border-[color-mix(in_srgb,var(--aegis-accent-line)_45%,var(--aegis-border-default))]',
          'bg-[color-mix(in_srgb,var(--aegis-surface-panel)_94%,transparent)] shadow-[var(--aegis-shadow-dialog)] backdrop-blur-xl',
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--aegis-focus-ring)]',
        )}
        data-testid="tutorial-coach-mark"
      >
        <div className="flex flex-col gap-3 p-5">
          <div className="flex items-center justify-between gap-3">
            <span className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-accent-strong)]')}>
              {step.eyebrow}
            </span>
            <span
              className={cn(typographyTokens.monoSm, 'text-[var(--aegis-text-faint)]')}
              aria-hidden="true"
            >
              {stepNumber} / {STEP_COUNT}
            </span>
          </div>

          <h2
            id={titleId}
            className="font-[family-name:var(--aegis-font-display)] text-lg font-semibold leading-6 tracking-[-0.005em] text-[var(--aegis-text-primary)]"
          >
            {step.title}
          </h2>

          <div id={bodyId} className="flex flex-col gap-2">
            {step.body.map((paragraph, index) => (
              <p
                key={index}
                className="text-[0.8125rem] leading-5 text-[var(--aegis-text-secondary)]"
              >
                {paragraph}
              </p>
            ))}
          </div>

          {step.advanceHint && !step.primaryAction ? (
            <p
              className={cn(
                typographyTokens.monoSm,
                'flex items-center gap-2 text-[var(--aegis-text-muted)]',
              )}
              data-testid="tutorial-advance-hint"
            >
              <span
                aria-hidden="true"
                className={cn(
                  'size-1.5 rounded-full bg-[var(--aegis-accent-cyan)]',
                  !reducedMotion && 'animate-pulse',
                )}
              />
              {step.advanceHint}
            </p>
          ) : null}

          <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              {step.primaryAction === 'begin' ? (
                <Button size="sm" onClick={onBegin} data-testid="tutorial-begin">
                  Begin walkthrough
                </Button>
              ) : null}
              {step.primaryAction === 'launch-next' ? (
                <Button size="sm" onClick={onLaunchNext} data-testid="tutorial-launch-next">
                  Launch Operation Silent Relay
                </Button>
              ) : null}
              {!step.primaryAction ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onSkipStep}
                  data-testid="tutorial-skip-step"
                >
                  Skip this step
                </Button>
              ) : null}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={onSkipTutorial}
              data-testid="tutorial-skip-tutorial"
            >
              {step.primaryAction === 'launch-next' ? 'Close' : 'Skip tutorial'}
            </Button>
          </div>
        </div>
      </div>

      <VisuallyHidden aria-live="polite" role="status">
        Guided run, step {stepNumber} of {STEP_COUNT}: {step.title}. Pointing at {step.pointerLabel}
        .
      </VisuallyHidden>
    </div>,
    document.body,
  );
}

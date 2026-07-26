'use client';

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import { Button, VisuallyHidden, cn, typographyTokens, useReducedMotion } from '@aegis/ui';

import type {
  ResolvedBeat,
  TutorialBeat,
  TutorialChapter,
  TutorialEvidence,
  TutorialObjective,
  TutorialProgress,
} from '../tutorial-contract';
import { ChapterMenu } from './chapter-menu';

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

interface Size {
  width: number;
  height: number;
}

interface Point {
  top: number;
  left: number;
}

export interface CoachMarkOverlayProps {
  resolved: ResolvedBeat;
  chapters: readonly TutorialChapter[];
  evidence: TutorialEvidence;
  progress: TutorialProgress;
  objectiveSatisfied: boolean;
  onNext: () => void;
  onBack: () => void;
  onSkipChapter: () => void;
  onJumpToChapter: (chapterId: string) => void;
  onMinimize: () => void;
  onRestore: () => void;
  onDismiss: () => void;
  onBegin: () => void;
  onLaunchNext: () => void;
}

const CARD_GAP = 14;
const VIEWPORT_MARGIN = 16;
const SPOTLIGHT_PADDING = 8;
/** How long the card is allowed to travel when a new beat moves the spotlight. */
const GLIDE_MS = 240;
/** Card size assumed before the element has been laid out (matches `w-[min(92vw,24rem)]`). */
const CARD_FALLBACK_SIZE: Size = { width: 384, height: 300 };

/** The lit region the card must stay off: the anchor plus the spotlight's own padding. */
export function spotlightRect(anchor: Rect): Rect {
  return {
    top: anchor.top - SPOTLIGHT_PADDING,
    left: anchor.left - SPOTLIGHT_PADDING,
    width: anchor.width + SPOTLIGHT_PADDING * 2,
    height: anchor.height + SPOTLIGHT_PADDING * 2,
  };
}

export function intersectionArea(a: Rect, b: Rect): number {
  const overlapWidth = Math.min(a.left + a.width, b.left + b.width) - Math.max(a.left, b.left);
  const overlapHeight = Math.min(a.top + a.height, b.top + b.height) - Math.max(a.top, b.top);
  if (overlapWidth <= 0 || overlapHeight <= 0) {
    return 0;
  }
  return overlapWidth * overlapHeight;
}

/**
 * Place the coach mark so it never sits on the thing it is pointing at.
 *
 * Non-occlusion is a hard constraint, not a preference. The card is offered the four sides
 * of the spotlight in reading order — below first, because that is where a callout is
 * expected — but a side is only taken when the free band there genuinely holds the whole
 * card. Nothing is clamped back across the spotlight to make it fit, which is exactly how
 * large anchors (the graph stage, a full dock, the status strip) used to end up buried
 * under the card.
 *
 * When no side holds the card the viewport corners are tried instead, which recovers the
 * L-shaped free space a side band misses. Only when every corner is blocked too — an
 * anchor with no clear band anywhere, i.e. one that all but fills the viewport — does the
 * card settle for the corner it covers the least of, so the degradation is deliberate and
 * bounded rather than a silent 97% burial.
 *
 * Pure and exported so the geometry is testable without a browser.
 */
export function computeCardPosition(anchor: Rect, card: Size, viewport: Size): Point {
  const spot = spotlightRect(anchor);
  const spotRight = spot.left + spot.width;
  const spotBottom = spot.top + spot.height;

  const minLeft = VIEWPORT_MARGIN;
  const minTop = VIEWPORT_MARGIN;
  const maxLeft = Math.max(VIEWPORT_MARGIN, viewport.width - card.width - VIEWPORT_MARGIN);
  const maxTop = Math.max(VIEWPORT_MARGIN, viewport.height - card.height - VIEWPORT_MARGIN);
  const clampLeft = (value: number) => Math.min(Math.max(value, minLeft), maxLeft);
  const clampTop = (value: number) => Math.min(Math.max(value, minTop), maxTop);

  const at = (point: Point): Rect => ({ ...point, width: card.width, height: card.height });
  const clear = (point: Point) => intersectionArea(at(point), spot) === 0;

  // Free space beside the spotlight, measured on the axis the card has to clear. Cross-axis
  // clamping is safe: a card below the spotlight cannot slide back into it sideways.
  const sides: { free: number; needed: number; place: () => Point }[] = [
    {
      free: viewport.height - VIEWPORT_MARGIN - (spotBottom + CARD_GAP),
      needed: card.height,
      place: () => ({ top: spotBottom + CARD_GAP, left: clampLeft(spot.left) }),
    },
    {
      free: spot.top - CARD_GAP - VIEWPORT_MARGIN,
      needed: card.height,
      place: () => ({ top: spot.top - CARD_GAP - card.height, left: clampLeft(spot.left) }),
    },
    {
      free: viewport.width - VIEWPORT_MARGIN - (spotRight + CARD_GAP),
      needed: card.width,
      place: () => ({ top: clampTop(spot.top), left: spotRight + CARD_GAP }),
    },
    {
      free: spot.left - CARD_GAP - VIEWPORT_MARGIN,
      needed: card.width,
      place: () => ({ top: clampTop(spot.top), left: spot.left - CARD_GAP - card.width }),
    },
  ];

  for (const side of sides) {
    if (side.free < side.needed) {
      continue;
    }
    const point = side.place();
    // The band arithmetic already guarantees this; the check is the guard that keeps a
    // future edit from reintroducing an overlapping placement.
    if (clear(point)) {
      return point;
    }
  }

  // Corners, furthest-from-the-spotlight first, so the fallback also reads as "out of the
  // way" rather than merely "not touching".
  const corners: Point[] = [
    { top: maxTop, left: maxLeft },
    { top: minTop, left: maxLeft },
    { top: maxTop, left: minLeft },
    { top: minTop, left: minLeft },
  ];

  let best = corners[0] ?? { top: minTop, left: minLeft };
  let bestArea = Number.POSITIVE_INFINITY;
  for (const corner of corners) {
    const area = intersectionArea(at(corner), spot);
    if (area === 0) {
      return corner;
    }
    if (area < bestArea) {
      best = corner;
      bestArea = area;
    }
  }
  return best;
}

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

function toRect(element: Element): Rect {
  const box = element.getBoundingClientRect();
  return { top: box.top, left: box.left, width: box.width, height: box.height };
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
 * Track the viewport rect of the first anchor selector that matches.
 *
 * Event-driven rather than polled: a `ResizeObserver` covers the anchor and the document
 * resizing, rAF-throttled scroll/resize listeners cover the camera moving, and a
 * `MutationObserver` covers the two DOM-shaped cases — an anchor that mounts after its
 * beat became active, and an anchor that is torn down while the beat is still showing.
 * While an anchor is resolved the mutation callback is a single `isConnected` check, so a
 * busy run surface does not pay for the subscription.
 */
function useAnchorRect(anchors: readonly string[], enabled: boolean): Rect | null {
  const [rect, setRect] = useState<Rect | null>(null);
  // Selector list identity is not stable across renders; the joined key is.
  const anchorKey = anchors.join('|');

  useEffect(() => {
    if (!enabled || typeof window === 'undefined') {
      return;
    }
    const selectors = anchorKey ? anchorKey.split('|') : [];
    let element: Element | null = null;
    let current: Rect | null = null;
    let frame: number | null = null;
    let disposed = false;

    let resizeObserver: ResizeObserver | null = null;

    const measure = () => {
      if (disposed) {
        return;
      }
      if (!element || !element.isConnected) {
        const next = resolveAnchor(selectors);
        if (next !== element) {
          element = next;
          resizeObserver?.disconnect();
          if (element && resizeObserver) {
            resizeObserver.observe(element);
            // Document-level resizes reflow the anchor without changing its own box.
            resizeObserver.observe(document.body);
          }
        }
      }
      const next = element ? toRect(element) : null;
      if (rectsDiffer(current, next)) {
        current = next;
        setRect(next);
      }
    };

    const schedule = () => {
      if (disposed || frame !== null) {
        return;
      }
      frame = window.requestAnimationFrame(() => {
        frame = null;
        measure();
      });
    };

    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(schedule);
    }

    measure();

    const mutationObserver =
      typeof MutationObserver === 'undefined'
        ? null
        : new MutationObserver(() => {
            if (element && element.isConnected) {
              return;
            }
            schedule();
          });
    mutationObserver?.observe(document.body, {
      childList: true,
      subtree: true,
    });

    window.addEventListener('scroll', schedule, true);
    window.addEventListener('resize', schedule);

    return () => {
      disposed = true;
      if (frame !== null) {
        window.cancelAnimationFrame(frame);
      }
      resizeObserver?.disconnect();
      mutationObserver?.disconnect();
      window.removeEventListener('scroll', schedule, true);
      window.removeEventListener('resize', schedule);
    };
  }, [anchorKey, enabled]);

  return rect;
}

function ChevronGlyph({ open }: { open: boolean }) {
  return (
    <svg
      aria-hidden="true"
      className="h-3.5 w-3.5 shrink-0"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={open ? 'm4 10 4-4 4 4' : 'm4 6 4 4 4-4'} />
    </svg>
  );
}

function CheckGlyph({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={cn('h-3 w-3', className)}
      viewBox="0 0 12 12"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M2.5 6.4 4.8 8.7 9.5 3.5" />
    </svg>
  );
}

/**
 * The chapter's beats as a segmented gauge: filled behind the operator, hollow ahead, the
 * current beat wide and lit. `do` beats whose evidence has already landed read green, so a
 * later objective the run has already satisfied is visible before the operator gets there.
 */
function BeatGauge({
  beats,
  beatNumber,
  chapterStartIndex,
  reached,
  evidence,
  reducedMotion,
  className,
}: {
  beats: readonly TutorialBeat[];
  beatNumber: number;
  chapterStartIndex: number;
  reached: number;
  evidence: TutorialEvidence;
  reducedMotion: boolean;
  className?: string;
}) {
  return (
    <div className={cn('flex items-center gap-1', className)} aria-hidden="true">
      {beats.map((beat, position) => {
        const isCurrent = position === beatNumber - 1;
        const visited = chapterStartIndex + position <= reached;
        const satisfied = beat.objective ? evidence[beat.objective.evidence] : false;
        return (
          <span
            key={beat.id}
            className={cn(
              'h-[3px] rounded-full',
              !reducedMotion &&
                'transition-[flex-grow,background-color] duration-[var(--aegis-motion-duration-normal)] ease-[var(--aegis-motion-ease-emphasis)]',
              isCurrent
                ? 'flex-[3] bg-[var(--aegis-accent-cyan)]'
                : satisfied
                  ? 'flex-1 bg-[var(--aegis-status-normal)]'
                  : visited
                    ? 'flex-1 bg-[var(--aegis-accent-line)]'
                    : 'flex-1 bg-[var(--aegis-border-default)]',
            )}
          />
        );
      })}
    </div>
  );
}

/**
 * The objective of a `do` beat, either side of the operator satisfying it.
 *
 * Everything that changes on completion — the frame, the glow, the marker, the label —
 * moves on one transition, so landing an objective reads as a single confirmation rather
 * than four independent flickers. Under reduced motion the same states are reached with no
 * transition at all.
 */
function ObjectiveCallout({
  objective,
  satisfied,
  reducedMotion,
}: {
  objective: TutorialObjective;
  satisfied: boolean;
  reducedMotion: boolean;
}) {
  const transition = reducedMotion
    ? undefined
    : 'transition-[background-color,border-color,box-shadow,color,opacity,transform] duration-[var(--aegis-motion-duration-slow)] ease-[var(--aegis-motion-ease-emphasis)]';

  return (
    <div
      data-testid="tutorial-objective"
      data-state={satisfied ? 'done' : 'pending'}
      className={cn(
        'flex items-start gap-2.5 rounded-[var(--aegis-radius-md)] border px-3 py-2.5',
        transition,
        satisfied
          ? 'border-[var(--aegis-status-normal)] bg-[var(--aegis-status-normal-bg)] shadow-[0_0_20px_-6px_var(--aegis-status-normal)]'
          : 'border-[var(--aegis-accent-line)] bg-[var(--aegis-accent-soft)] shadow-none',
      )}
    >
      <span
        className={cn(
          'relative mt-[0.1875rem] flex size-4 shrink-0 items-center justify-center rounded-full border',
          transition,
          satisfied
            ? 'border-[var(--aegis-status-normal)] bg-[var(--aegis-status-normal)]'
            : 'border-[var(--aegis-accent-cyan)] bg-transparent',
        )}
      >
        <span
          className={cn(
            'size-1.5 rounded-full bg-[var(--aegis-accent-cyan)]',
            transition,
            satisfied ? 'opacity-0' : 'opacity-100',
            !satisfied && !reducedMotion && 'animate-pulse',
          )}
        />
        <CheckGlyph
          className={cn(
            'absolute text-[var(--aegis-status-normal-bg)]',
            transition,
            satisfied ? 'scale-100 opacity-100' : 'scale-50 opacity-0',
          )}
        />
      </span>
      <div className="flex min-w-0 flex-col gap-0.5">
        <span
          className={cn(
            typographyTokens.eyebrow,
            transition,
            satisfied ? 'text-[var(--aegis-status-normal)]' : 'text-[var(--aegis-accent-strong)]',
          )}
        >
          {satisfied ? 'Objective met' : 'Objective'}
        </span>
        <p
          data-testid="tutorial-advance-hint"
          className={cn(typographyTokens.bodySm, 'text-[var(--aegis-text-secondary)]')}
        >
          {satisfied ? objective.done : objective.pending}
        </p>
      </div>
    </div>
  );
}

/**
 * Anchored spotlight + callout card for one walkthrough beat.
 *
 * The dimming layer never captures pointer events, so every highlighted control stays
 * clickable — the operator can act on the very thing being pointed at without dismissing
 * the coach mark, which is the entire point of the spotlight. Focus is never trapped for
 * the same reason. When a beat's anchor is absent from the DOM the card renders centred in
 * a degraded-but-usable mode with the same copy and controls.
 *
 * Progress is soft-gated: Next is always live. Several objectives can only be satisfied
 * once the simulation produces the evidence, and a hard gate would strand the operator.
 * Escape collapses the card to its pill rather than ending the walkthrough — dismissing is
 * a deliberate, separate control.
 */
export function CoachMarkOverlay({
  resolved,
  chapters,
  evidence,
  progress,
  objectiveSatisfied,
  onNext,
  onBack,
  onSkipChapter,
  onJumpToChapter,
  onMinimize,
  onRestore,
  onDismiss,
  onBegin,
  onLaunchNext,
}: CoachMarkOverlayProps) {
  const reducedMotion = useReducedMotion();
  const [mounted, setMounted] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [cardPos, setCardPos] = useState<{ top: number; left: number } | null>(null);
  const [glide, setGlide] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const cardPosRef = useRef<{ top: number; left: number } | null>(null);

  const { beat, chapter, index, beatNumber, beatCount, chapterNumber, chapterCount } = resolved;
  const minimized = progress.minimized;

  useEffect(() => {
    setMounted(true);
  }, []);

  const anchorRect = useAnchorRect(beat.anchors, mounted && !minimized);

  // Place the card clear of the spotlight. Centred when there is no anchor to sit beside.
  // Re-runs on `menuOpen` too: opening the chapter list changes the card's height, and a
  // stale height is how a card that fitted below an anchor stops fitting.
  useLayoutEffect(() => {
    if (!anchorRect || minimized) {
      cardPosRef.current = null;
      setCardPos(null);
      return;
    }
    const card = cardRef.current;
    const next = computeCardPosition(
      anchorRect,
      {
        // `||` not `??`: an unlaid-out element measures 0, which is not a usable size.
        width: card?.offsetWidth || CARD_FALLBACK_SIZE.width,
        height: card?.offsetHeight || CARD_FALLBACK_SIZE.height,
      },
      {
        width: window.innerWidth || 1280,
        height: window.innerHeight || 800,
      },
    );
    cardPosRef.current = next;
    setCardPos(next);
  }, [anchorRect, beat.id, minimized, menuOpen]);

  // Travel between anchors is worth animating; every rect update is not. The transition is
  // armed only for the moment after a beat change, so the card glides to its new anchor and
  // then tracks layout movement instantly instead of chasing it.
  useEffect(() => {
    if (!cardPosRef.current || reducedMotion) {
      return;
    }
    setGlide(true);
    const timer = window.setTimeout(() => {
      setGlide(false);
    }, GLIDE_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [beat.id, reducedMotion]);

  // Close the chapter list whenever the beat moves on under it.
  useEffect(() => {
    setMenuOpen(false);
  }, [beat.id]);

  // Take focus when the card appears — on first mount and on restore from the pill — but
  // never on a beat change, which is often the run satisfying an objective while the
  // operator is mid-interaction somewhere else in the app.
  useEffect(() => {
    if (!mounted || minimized) {
      return;
    }
    const frame = window.requestAnimationFrame(() => {
      cardRef.current?.focus();
    });
    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [mounted, minimized]);

  const closeMenu = useCallback(() => {
    setMenuOpen(false);
    triggerRef.current?.focus();
  }, []);

  const handleSelectChapter = useCallback(
    (chapterId: string) => {
      setMenuOpen(false);
      onJumpToChapter(chapterId);
    },
    [onJumpToChapter],
  );

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      // Enter on a control is that control's business; only treat it as "next" when the
      // operator is on the card itself.
      const target = event.target;
      const onControl =
        target instanceof HTMLElement &&
        (['BUTTON', 'A', 'INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) ||
          target.isContentEditable);

      switch (event.key) {
        case 'Escape':
          event.preventDefault();
          event.stopPropagation();
          onMinimize();
          return;
        case 'ArrowRight':
          event.preventDefault();
          onNext();
          return;
        case 'ArrowLeft':
          event.preventDefault();
          if (index > 0) {
            onBack();
          }
          return;
        case 'Enter':
          if (!onControl) {
            event.preventDefault();
            onNext();
          }
          return;
        default:
      }
    },
    [index, onBack, onMinimize, onNext],
  );

  const chapterStartIndex = index - (beatNumber - 1);
  const positionLabel = `Chapter ${String(chapterNumber)} of ${String(chapterCount)} · Beat ${String(beatNumber)} of ${String(beatCount)}`;

  const announcement = useMemo(() => {
    const objectiveLine = beat.objective
      ? objectiveSatisfied
        ? ` Objective met: ${beat.objective.done}`
        : ` Objective: ${beat.objective.pending}`
      : '';
    return `Chapter ${String(chapterNumber)} of ${String(chapterCount)}, ${chapter.title}. Beat ${String(beatNumber)} of ${String(beatCount)}: ${beat.title}. Pointing at ${beat.pointerLabel}.${objectiveLine}`;
  }, [
    beat.objective,
    beat.pointerLabel,
    beat.title,
    beatCount,
    beatNumber,
    chapter.title,
    chapterCount,
    chapterNumber,
    objectiveSatisfied,
  ]);

  if (!mounted) {
    return null;
  }

  const menuId = 'tutorial-chapter-menu-panel';
  const titleId = `tutorial-beat-title-${beat.id}`;
  const bodyId = `tutorial-beat-body-${beat.id}`;
  const isCentered = anchorRect == null;

  // Drawn from the same rect the placement engine treats as off-limits, so what the
  // operator sees lit is exactly what the card is guaranteed to stay off.
  const spotlightBox: React.CSSProperties | null = anchorRect
    ? { position: 'fixed', ...spotlightRect(anchorRect), borderRadius: 'var(--aegis-radius-lg)' }
    : null;

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
        transition: glide
          ? `top ${String(GLIDE_MS)}ms var(--aegis-motion-ease-emphasis), left ${String(GLIDE_MS)}ms var(--aegis-motion-ease-emphasis)`
          : undefined,
      };

  const gauge = (
    <BeatGauge
      beats={chapter.beats}
      beatNumber={beatNumber}
      chapterStartIndex={chapterStartIndex}
      reached={progress.reached}
      evidence={evidence}
      reducedMotion={reducedMotion}
    />
  );

  return createPortal(
    <div
      className="pointer-events-none fixed inset-0 z-[120]"
      data-testid="tutorial-overlay"
      data-tutorial-beat={beat.id}
      data-tutorial-chapter={chapter.id}
    >
      {minimized ? null : isCentered ? (
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-[color-mix(in_srgb,var(--aegis-surface-base)_60%,transparent)] backdrop-blur-[2px]"
        />
      ) : (
        <>
          <div
            aria-hidden="true"
            style={{
              ...spotlightBox,
              boxShadow:
                '0 0 0 9999px color-mix(in srgb, var(--aegis-surface-base) 68%, transparent)',
            }}
          />
          <div
            aria-hidden="true"
            style={spotlightBox ?? undefined}
            className={cn(
              'ring-2 ring-[var(--aegis-accent-line)] ring-offset-0',
              'shadow-[0_0_0_1px_var(--aegis-accent-strong),0_0_24px_color-mix(in_srgb,var(--aegis-accent-cyan)_40%,transparent)]',
              !reducedMotion && 'animate-pulse',
            )}
          />
        </>
      )}

      {minimized ? (
        <button
          type="button"
          onClick={onRestore}
          data-testid="tutorial-restore"
          aria-label={`Reopen the walkthrough. ${positionLabel.replace(' · ', ', ')}, ${chapter.title}.`}
          className={cn(
            'pointer-events-auto fixed bottom-4 right-4 flex max-w-[min(80vw,17rem)] items-center gap-3',
            'rounded-full border border-[color-mix(in_srgb,var(--aegis-accent-line)_45%,var(--aegis-border-default))]',
            'bg-[color-mix(in_srgb,var(--aegis-surface-panel)_92%,transparent)] py-2 pl-3 pr-4 text-left',
            'shadow-[var(--aegis-shadow-dialog)] backdrop-blur-xl',
            'hover:border-[var(--aegis-accent-line)] hover:bg-[var(--aegis-surface-hover)]',
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--aegis-focus-ring)]',
          )}
        >
          <span
            aria-hidden="true"
            className={cn(
              'size-2 shrink-0 rounded-full',
              beat.objective && !objectiveSatisfied
                ? cn('bg-[var(--aegis-accent-cyan)]', !reducedMotion && 'animate-pulse')
                : beat.objective
                  ? 'bg-[var(--aegis-status-normal)]'
                  : 'bg-[var(--aegis-accent-line)]',
            )}
          />
          <span className="flex min-w-0 flex-col gap-1" aria-hidden="true">
            <span className="flex items-baseline gap-2">
              <span
                className={cn(
                  typographyTokens.monoSm,
                  'shrink-0 text-[var(--aegis-accent-strong)]',
                )}
              >
                {chapterNumber}/{chapterCount}
              </span>
              <span
                className={cn(
                  typographyTokens.bodySm,
                  'truncate font-medium text-[var(--aegis-text-primary)]',
                )}
              >
                {chapter.title}
              </span>
            </span>
            {gauge}
          </span>
        </button>
      ) : (
        <div
          ref={cardRef}
          role="dialog"
          aria-modal="false"
          aria-labelledby={menuOpen ? `${menuId}-heading` : titleId}
          aria-describedby={menuOpen ? undefined : bodyId}
          tabIndex={-1}
          onKeyDown={handleKeyDown}
          style={cardStyle}
          className={cn(
            'pointer-events-auto flex w-[min(92vw,24rem)] max-h-[calc(100vh-2rem)] flex-col overflow-hidden',
            'rounded-[var(--aegis-radius-xl)]',
            'border border-[color-mix(in_srgb,var(--aegis-accent-line)_45%,var(--aegis-border-default))]',
            'bg-[color-mix(in_srgb,var(--aegis-surface-panel)_94%,transparent)] shadow-[var(--aegis-shadow-dialog)] backdrop-blur-xl',
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--aegis-focus-ring)]',
          )}
          data-testid="tutorial-coach-mark"
        >
          <div className="flex flex-col gap-2 px-5 pt-4">
            <div className="flex items-start justify-between gap-2">
              <span
                className={cn(
                  typographyTokens.eyebrow,
                  'mt-1.5 min-w-0 truncate text-[var(--aegis-accent-strong)]',
                )}
              >
                {chapter.title}
              </span>
              <div className="-mr-2 flex shrink-0 items-center">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={onMinimize}
                  aria-label="Minimize the walkthrough"
                  data-testid="tutorial-minimize"
                >
                  <svg
                    aria-hidden="true"
                    className="h-4 w-4"
                    viewBox="0 0 16 16"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                  >
                    <path d="M4 11h8" />
                  </svg>
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={onDismiss}
                  aria-label="End the walkthrough"
                  data-testid="tutorial-dismiss"
                >
                  <svg
                    aria-hidden="true"
                    className="h-4 w-4"
                    viewBox="0 0 16 16"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                  >
                    <path d="m4.5 4.5 7 7m0-7-7 7" />
                  </svg>
                </Button>
              </div>
            </div>
            {gauge}
          </div>

          {menuOpen ? (
            <div className="flex min-h-0 flex-col px-5 py-4">
              <ChapterMenu
                id={menuId}
                chapters={chapters}
                activeChapterId={chapter.id}
                reached={progress.reached}
                onSelect={handleSelectChapter}
                onClose={closeMenu}
              />
            </div>
          ) : (
            <div className="flex min-h-0 flex-col gap-3 overflow-y-auto px-5 py-4">
              <h2
                id={titleId}
                className={cn(typographyTokens.displayLg, 'text-[var(--aegis-text-primary)]')}
              >
                {beat.title}
              </h2>

              <div id={bodyId} className="flex flex-col gap-2">
                {beat.body.map((paragraph, position) => (
                  <p
                    key={position}
                    className={cn(typographyTokens.bodySm, 'text-[var(--aegis-text-secondary)]')}
                  >
                    {paragraph}
                  </p>
                ))}
              </div>

              {beat.objective ? (
                <ObjectiveCallout
                  key={beat.id}
                  objective={beat.objective}
                  satisfied={objectiveSatisfied}
                  reducedMotion={reducedMotion}
                />
              ) : null}

              {beat.primaryAction === 'begin' ? (
                <Button onClick={onBegin} data-testid="tutorial-begin">
                  Begin walkthrough
                </Button>
              ) : null}
              {beat.primaryAction === 'launch-next' ? (
                <Button onClick={onLaunchNext} data-testid="tutorial-launch-next">
                  Launch Operation Silent Relay
                </Button>
              ) : null}
            </div>
          )}

          <div className="flex flex-col gap-2 border-t border-[var(--aegis-border-subtle)] px-5 py-3">
            <button
              ref={triggerRef}
              type="button"
              onClick={() => {
                setMenuOpen((open) => !open);
              }}
              aria-expanded={menuOpen}
              // Only advertised while the panel exists; a dangling reference is worse than none.
              aria-controls={menuOpen ? menuId : undefined}
              data-testid="tutorial-chapter-menu-trigger"
              className={cn(
                typographyTokens.monoSm,
                'flex w-full items-center justify-between gap-2 rounded-[var(--aegis-radius-sm)] px-1 py-1',
                'text-[var(--aegis-text-muted)] transition-colors duration-[var(--aegis-motion-duration-fast)]',
                'hover:bg-[var(--aegis-surface-hover)] hover:text-[var(--aegis-text-primary)]',
                'focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--aegis-focus-ring)]',
              )}
            >
              <span>{positionLabel}</span>
              <span className="flex items-center gap-1.5">
                {menuOpen ? 'Close list' : 'All chapters'}
                <ChevronGlyph open={menuOpen} />
              </span>
            </button>

            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onBack}
                  disabled={index === 0}
                  data-testid="tutorial-back"
                >
                  Back
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onSkipChapter}
                  data-testid="tutorial-skip-chapter"
                >
                  Skip chapter
                </Button>
              </div>
              <Button
                variant={beat.primaryAction ? 'secondary' : 'default'}
                size="sm"
                onClick={onNext}
                data-testid="tutorial-next"
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}

      <VisuallyHidden aria-live="polite" role="status">
        {announcement}
      </VisuallyHidden>
    </div>,
    document.body,
  );
}

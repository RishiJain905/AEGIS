'use client';

import { useCallback, useEffect, useMemo, useRef } from 'react';

import { Button, cn, typographyTokens } from '@aegis/ui';

import type { TutorialChapter } from '../tutorial-contract';

/** Where a chapter sits relative to the operator's furthest progress. */
export type ChapterProgressState = 'complete' | 'current' | 'started' | 'upcoming';

interface ChapterEntry {
  chapter: TutorialChapter;
  /** 1-based position across the whole walkthrough, used as the visible marker. */
  number: number;
  /** Absolute index of the chapter's first beat. */
  startIndex: number;
  state: ChapterProgressState;
  /** How many of the chapter's beats the operator has reached. */
  beatsVisited: number;
}

export interface ChapterMenuProps {
  chapters: readonly TutorialChapter[];
  /** Chapter the walkthrough is currently sitting in. */
  activeChapterId: string;
  /** Furthest absolute beat index ever visited (`TutorialProgress.reached`). */
  reached: number;
  /** DOM id, so the opening control can point `aria-controls` at the list. */
  id: string;
  onSelect: (chapterId: string) => void;
  onClose: () => void;
}

const SECTIONS = [
  {
    key: 'cockpit' as const,
    label: 'Cockpit',
    hint: 'The run workspace, in depth.',
  },
  {
    key: 'tour' as const,
    label: 'Tour',
    hint: 'Brief passes over the rest of the app.',
  },
];

const OPTION_SELECTOR = 'button[data-chapter-option]';

function CheckGlyph() {
  return (
    <svg
      aria-hidden="true"
      className="h-3 w-3"
      viewBox="0 0 12 12"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M2.5 6.4 4.8 8.7 9.5 3.5" />
    </svg>
  );
}

function describeState(entry: ChapterEntry): string {
  switch (entry.state) {
    case 'complete':
      return 'Complete';
    case 'current':
      return 'You are here';
    case 'started':
      return `${String(entry.beatsVisited)} of ${String(entry.chapter.beats.length)} beats`;
    default:
      return `${String(entry.chapter.beats.length)} beats`;
  }
}

function buildEntries(
  chapters: readonly TutorialChapter[],
  activeChapterId: string,
  reached: number,
): ChapterEntry[] {
  let startIndex = 0;
  return chapters.map((chapter, position) => {
    const start = startIndex;
    const length = chapter.beats.length;
    startIndex += length;
    const endIndex = start + length - 1;
    const state: ChapterProgressState =
      chapter.id === activeChapterId
        ? 'current'
        : reached > endIndex
          ? 'complete'
          : reached >= start
            ? 'started'
            : 'upcoming';
    return {
      chapter,
      number: position + 1,
      startIndex: start,
      state,
      beatsVisited: Math.min(Math.max(reached - start + 1, 0), length),
    };
  });
}

/**
 * The walkthrough's table of contents.
 *
 * An operator who already knows the cockpit should be able to land straight on the part
 * they came for, so every chapter is listed with its summary and how far through it they
 * are — grouped by `section` so the deep cockpit chapters read separately from the quick
 * passes over the rest of the app.
 *
 * Rendered inside the coach mark's own dialog rather than as a second floating layer:
 * one surface, one focus context. Arrow keys rove between chapters, Escape closes the
 * list and hands focus back to the control that opened it — never tearing down the
 * walkthrough itself.
 */
export function ChapterMenu({
  chapters,
  activeChapterId,
  reached,
  id,
  onSelect,
  onClose,
}: ChapterMenuProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const headingId = `${id}-heading`;

  const entries = useMemo(
    () => buildEntries(chapters, activeChapterId, reached),
    [chapters, activeChapterId, reached],
  );

  const options = useCallback((): HTMLButtonElement[] => {
    const root = containerRef.current;
    if (!root) {
      return [];
    }
    return Array.from(root.querySelectorAll<HTMLButtonElement>(OPTION_SELECTOR));
  }, []);

  // Open on the chapter the operator is in — the list should start where they are, not at
  // the top, so "where am I" and "where could I go" are answered in one glance.
  useEffect(() => {
    const items = options();
    const current = items.find((item) => item.dataset.chapterState === 'current');
    (current ?? items[0])?.focus();
  }, [options]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      // The menu owns every key it reacts to; the coach mark's own shortcuts must not also
      // fire while the operator is browsing chapters.
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key === 'Enter' || event.key === ' ') {
        event.stopPropagation();
        return;
      }
      if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
        return;
      }
      const items = options();
      if (items.length === 0) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      const active = document.activeElement;
      const index = items.findIndex((item) => item === active);
      const next =
        event.key === 'Home'
          ? 0
          : event.key === 'End'
            ? items.length - 1
            : event.key === 'ArrowDown'
              ? (index + 1 + items.length) % items.length
              : (index - 1 + items.length) % items.length;
      items[next]?.focus();
    },
    [onClose, options],
  );

  return (
    <div
      ref={containerRef}
      id={id}
      role="group"
      aria-labelledby={headingId}
      onKeyDown={handleKeyDown}
      className="flex min-h-0 flex-col gap-2"
      data-testid="tutorial-chapter-menu"
    >
      <div className="flex items-center justify-between gap-2">
        <h3
          id={headingId}
          className={cn(typographyTokens.displayMd, 'text-[var(--aegis-text-primary)]')}
        >
          Jump to chapter
        </h3>
        <Button
          variant="ghost"
          size="sm"
          className="min-h-8"
          onClick={onClose}
          data-testid="tutorial-chapter-menu-close"
        >
          Close
        </Button>
      </div>

      <div className="-mr-1 flex max-h-[min(22rem,50vh)] flex-col gap-4 overflow-y-auto pr-1">
        {SECTIONS.map((section) => {
          const sectionEntries = entries.filter((entry) => entry.chapter.section === section.key);
          if (sectionEntries.length === 0) {
            return null;
          }
          const sectionId = `${id}-section-${section.key}`;
          return (
            <section key={section.key} aria-labelledby={sectionId}>
              <div className="mb-1.5 flex items-baseline gap-2">
                <h4
                  id={sectionId}
                  className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-accent-strong)]')}
                >
                  {section.label}
                </h4>
                <span
                  className={cn(typographyTokens.bodySm, 'text-[var(--aegis-text-faint)]')}
                  aria-hidden="true"
                >
                  {section.hint}
                </span>
              </div>
              <ul className="flex flex-col gap-1">
                {sectionEntries.map((entry) => (
                  <li key={entry.chapter.id}>
                    <button
                      type="button"
                      data-chapter-option=""
                      data-chapter-state={entry.state}
                      data-testid={`tutorial-chapter-option-${entry.chapter.id}`}
                      aria-current={entry.state === 'current' ? 'step' : undefined}
                      onClick={() => {
                        onSelect(entry.chapter.id);
                      }}
                      className={cn(
                        'group flex w-full items-start gap-3 border-l-2 py-2 pl-3 pr-2 text-left',
                        'rounded-r-[var(--aegis-radius-sm)] transition-colors duration-[var(--aegis-motion-duration-fast)]',
                        'hover:bg-[var(--aegis-surface-hover)]',
                        'focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--aegis-focus-ring)]',
                        entry.state === 'current'
                          ? 'border-[var(--aegis-accent-cyan)] bg-[var(--aegis-accent-soft)]'
                          : entry.state === 'complete'
                            ? 'border-[var(--aegis-status-normal)]'
                            : 'border-[var(--aegis-border-default)]',
                      )}
                    >
                      <span
                        className={cn(
                          typographyTokens.monoSm,
                          'mt-[0.1875rem] shrink-0',
                          entry.state === 'current'
                            ? 'text-[var(--aegis-accent-strong)]'
                            : 'text-[var(--aegis-text-faint)]',
                        )}
                        aria-hidden="true"
                      >
                        {String(entry.number).padStart(2, '0')}
                      </span>
                      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                        <span
                          className={cn(
                            typographyTokens.bodyMd,
                            'font-medium text-[var(--aegis-text-primary)]',
                          )}
                        >
                          {entry.chapter.title}
                        </span>
                        <span
                          className={cn(typographyTokens.bodySm, 'text-[var(--aegis-text-muted)]')}
                        >
                          {entry.chapter.summary}
                        </span>
                      </span>
                      <span
                        className={cn(
                          typographyTokens.monoSm,
                          'mt-[0.1875rem] flex shrink-0 items-center gap-1 text-right',
                          entry.state === 'complete'
                            ? 'text-[var(--aegis-status-normal)]'
                            : entry.state === 'current'
                              ? 'text-[var(--aegis-accent-strong)]'
                              : 'text-[var(--aegis-text-faint)]',
                        )}
                      >
                        {entry.state === 'complete' ? <CheckGlyph /> : null}
                        {describeState(entry)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    </div>
  );
}

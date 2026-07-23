'use client';

import Link from 'next/link';
import { useCallback, useMemo, useState, type HTMLAttributes, type ReactNode } from 'react';

import type {
  AfterActionViewModelV1,
  DecisionReviewV1,
  MissedEvidenceItemV1,
  ScoreComponentV1,
  ScoreExplanationV1,
  ScoreGradeBand,
  ValidAlternativeV1,
} from '@aegis/contracts-ts';
import { Badge, Button, EmptyState, LoadingState, cn, typographyTokens } from '@aegis/ui';

import { AdversaryDossier } from '@/features/after-action/dossier/adversary-dossier';
import { useAfterActionView } from '@/features/after-action/use-after-action-queries';
import {
  MetaRow,
  MonoChip,
  Pill,
  ScoreMeter,
  SectionLabel,
  scoreBand,
} from '@/features/reports/report-ui';
import { ApiClientError } from '@/lib/api/types';

/* ------------------------------------------------------------------ */
/* Local presentation helpers                                          */
/* ------------------------------------------------------------------ */

/**
 * A floating frosted surface — the single continuous container the whole
 * debrief is built from. Replaces the old per-section `Panel` boxes so related
 * content can share one surface with quiet internal separators instead of
 * stacking heavy equal-weight cards.
 */
function Surface({ className, children, ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={cn(
        'relative overflow-hidden rounded-[var(--aegis-radius-xl)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-panel)] shadow-[var(--aegis-shadow-panel)]',
        'before:pointer-events-none before:absolute before:inset-x-0 before:top-0 before:h-px before:bg-[var(--aegis-border-highlight)]',
        className,
      )}
      {...props}
    >
      {children}
    </section>
  );
}

/**
 * A quiet zone eyebrow with a trailing hairline rule — used to delineate zones
 * *inside* a shared surface rather than nesting bordered card-in-card boxes.
 */
function ZoneHeading({
  children,
  count,
  className,
}: {
  children: ReactNode;
  count?: number;
  className?: string;
}) {
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <h2
        className={cn(typographyTokens.displayMd, 'flex-none text-[var(--aegis-text-secondary)]')}
      >
        {children}
      </h2>
      {typeof count === 'number' ? (
        <span className="flex-none rounded-full bg-[var(--aegis-surface-raised)] px-1.5 py-0.5 font-mono text-[0.65rem] leading-none text-[var(--aegis-text-muted)] tabular-nums">
          {count}
        </span>
      ) : null}
      <span className="h-px flex-1 bg-[var(--aegis-border-subtle)]" />
    </div>
  );
}

/**
 * A list whose items are separated by hairlines instead of each sitting in its
 * own bordered box. This is the consistent "quiet row" treatment that replaces
 * the repeated `rounded border border-subtle` sub-card idiom.
 */
function QuietList({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('divide-y divide-[var(--aegis-border-subtle)]', className)} {...props}>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Grade                                                               */
/* ------------------------------------------------------------------ */

const GRADE_CLASS: Record<ScoreGradeBand, string> = {
  A: 'text-[var(--aegis-status-normal)] border-[var(--aegis-status-normal)]/40 bg-[var(--aegis-status-normal-bg)]',
  B: 'text-[var(--aegis-accent-cyan)] border-[var(--aegis-accent-line)]/50 bg-[var(--aegis-accent-soft)]',
  C: 'text-[var(--aegis-status-suspicious)] border-[var(--aegis-status-suspicious)]/40 bg-[var(--aegis-status-suspicious-bg)]',
  D: 'text-[var(--aegis-risk-high)] border-[var(--aegis-risk-high)]/40 bg-[var(--aegis-risk-high-bg)]',
  F: 'text-[var(--aegis-status-compromised)] border-[var(--aegis-status-compromised)]/40 bg-[var(--aegis-status-compromised-bg)]',
};

/* ------------------------------------------------------------------ */
/* Score component row                                                 */
/* ------------------------------------------------------------------ */

function ComponentRow({
  component,
  selected,
  onSelect,
}: {
  component: ScoreComponentV1;
  selected: boolean;
  onSelect: () => void;
}) {
  const pct = Math.round(component.rawScore * 100);
  return (
    <button
      type="button"
      data-testid={`score-component-${component.criterionId}`}
      aria-pressed={selected}
      onClick={onSelect}
      className={cn(
        'group relative w-full px-3 py-3 text-left transition-colors',
        'focus-visible:outline-none focus-visible:ring-[length:var(--aegis-focus-width)] focus-visible:ring-inset focus-visible:ring-[var(--aegis-focus-ring)]',
        selected
          ? 'bg-[var(--aegis-surface-raised)] shadow-[inset_2px_0_0_var(--aegis-accent-line)]'
          : 'hover:bg-[var(--aegis-surface-hover)]',
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <span
          className="truncate text-sm font-medium text-[var(--aegis-text-primary)]"
          title={component.label}
        >
          {component.label}
        </span>
        <span
          className={cn(
            'flex-none font-mono text-sm font-semibold tabular-nums',
            scoreBand(pct).text,
          )}
        >
          {pct}%
        </span>
      </div>
      <ScoreMeter value={component.rawScore} label={component.label} hideValue className="mt-2" />
      <div className="mt-2 flex items-center gap-3 text-[0.7rem] text-[var(--aegis-text-muted)]">
        <span>
          weight{' '}
          <span className="font-mono tabular-nums text-[var(--aegis-text-secondary)]">
            {component.weight.toFixed(2)}
          </span>
        </span>
        <span className="h-3 w-px bg-[var(--aegis-border-subtle)]" />
        <span>
          contribution{' '}
          <span className="font-mono tabular-nums text-[var(--aegis-text-secondary)]">
            {component.weightedContribution.toFixed(1)}
          </span>
        </span>
      </div>
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Explanation                                                         */
/* ------------------------------------------------------------------ */

function IdList({ label, ids }: { label: string; ids: readonly string[] }) {
  if (ids.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-muted)]')}>
        {label}
      </span>
      {ids.map((id) => (
        <MonoChip key={id} value={id} label={`${label} id`} />
      ))}
    </div>
  );
}

function ExplanationPanel({
  explanation,
  runId,
}: {
  explanation: ScoreExplanationV1;
  runId: string;
}) {
  return (
    <div data-testid="score-explanation" className="space-y-3">
      <div className="flex items-center gap-2">
        <span className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-muted)]')}>Rule</span>
        <span data-testid="score-rule-id">
          <MonoChip value={explanation.ruleId} label="rule id" />
        </span>
      </div>
      <p className="text-sm leading-6 text-[var(--aegis-text-secondary)]">{explanation.reason}</p>
      <IdList label="Events" ids={explanation.eventIds} />
      <IdList label="Evidence" ids={explanation.evidenceIds} />
      {explanation.sequence != null ? (
        <div className="pt-1">
          <Button asChild size="sm" data-testid="jump-to-replay">
            <Link href={`/replay/${runId}?sequence=${String(explanation.sequence)}`}>
              Jump to replay · seq {explanation.sequence}
            </Link>
          </Button>
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Decisions / evidence / alternatives                                 */
/* ------------------------------------------------------------------ */

const DECISION_OUTCOME_TONE: Record<DecisionReviewV1['outcome'], 'accent' | 'warning' | 'neutral'> =
  {
    credited: 'accent',
    restraint_credited: 'accent',
    penalized: 'warning',
    neutral: 'neutral',
  };

function DecisionRow({ review }: { review: DecisionReviewV1 }) {
  return (
    <div data-testid={`decision-review-${review.decisionId}`} className="py-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <Pill>{review.kind}</Pill>
        <Pill tone={DECISION_OUTCOME_TONE[review.outcome]}>{review.outcome.replace('_', ' ')}</Pill>
        <span className="ml-auto font-mono text-[0.7rem] text-[var(--aegis-text-muted)] tabular-nums">
          seq {review.sequence}
        </span>
      </div>
      <p className="mt-2 text-sm leading-5 text-[var(--aegis-text-primary)]">
        Operator <strong className="font-semibold">{review.operatorAction}</strong>
        {review.agentRecommendation ? (
          <>
            {' '}
            vs agent{' '}
            <em className="text-[var(--aegis-text-secondary)]">{review.agentRecommendation}</em>
          </>
        ) : null}
      </p>
      {review.availableInfoSummary ? (
        <p className="mt-1 text-xs leading-5 text-[var(--aegis-text-muted)]">
          {review.availableInfoSummary}
        </p>
      ) : null}
    </div>
  );
}

function TimelineRow({
  item,
  runId,
}: {
  item: AfterActionViewModelV1['timelineHighlights'][number];
  runId: string;
}) {
  return (
    <div
      className="flex items-center gap-3 py-2.5"
      data-testid={`timeline-highlight-${String(item.sequence)}`}
    >
      <span className="flex-none rounded bg-[var(--aegis-surface-raised)] px-1.5 py-0.5 font-mono text-[0.65rem] leading-none text-[var(--aegis-text-muted)] tabular-nums">
        {item.sequence}
      </span>
      <span
        className="min-w-0 flex-1 truncate text-sm text-[var(--aegis-text-primary)]"
        title={item.label}
      >
        {item.label}
      </span>
      <Button asChild size="sm" variant="ghost" className="flex-none px-2 text-xs">
        <Link href={`/replay/${runId}?sequence=${String(item.sequence)}`}>Replay</Link>
      </Button>
    </div>
  );
}

function MissedEvidenceRow({ item }: { item: MissedEvidenceItemV1 }) {
  return (
    <div
      data-testid={`missed-evidence-${item.expectedEvidenceKey}`}
      className="border-l-2 border-l-[var(--aegis-status-suspicious)] py-2.5 pl-3"
    >
      <div className="flex items-center justify-between gap-2">
        <span
          className="truncate text-sm font-medium text-[var(--aegis-text-primary)]"
          title={item.expectedEvidenceKey}
        >
          {item.expectedEvidenceKey}
        </span>
        <Pill tone="warning">missed</Pill>
      </div>
      {item.description ? (
        <p className="mt-1 text-xs leading-5 text-[var(--aegis-text-muted)]">{item.description}</p>
      ) : null}
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <Pill>{item.eventType}</Pill>
        {item.assetId ? <MonoChip value={item.assetId} label="asset id" /> : null}
        {item.bookmarkSequence != null ? (
          <span className="font-mono text-[0.7rem] text-[var(--aegis-text-muted)] tabular-nums">
            seq {String(item.bookmarkSequence)}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function AlternativeRow({ alt }: { alt: ValidAlternativeV1 }) {
  const positive = alt.scoreDelta > 0;
  return (
    <div data-testid={`valid-alternative-${alt.alternativeId}`} className="py-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <span
          data-testid="counterfactual-label"
          className="inline-flex min-h-5 items-center rounded-full border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-raised)] px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-[0.04em] text-[var(--aegis-text-muted)]"
        >
          non-authoritative
        </span>
        <Pill>{alt.kind.replace(/_/g, ' ')}</Pill>
      </div>
      <p className="mt-2 text-sm font-medium text-[var(--aegis-text-primary)]">{alt.label}</p>
      {alt.description ? (
        <p className="mt-1 text-xs leading-5 text-[var(--aegis-text-muted)]">{alt.description}</p>
      ) : null}
      <div className="mt-2 flex items-center gap-2 text-xs">
        <span className="text-[var(--aegis-text-muted)]">Projected</span>
        <span className="font-mono font-semibold tabular-nums text-[var(--aegis-text-primary)]">
          {alt.projectedOverallScore}
        </span>
        <span
          className={cn(
            'font-mono font-semibold tabular-nums',
            positive
              ? 'text-[var(--aegis-status-normal)]'
              : 'text-[var(--aegis-status-compromised)]',
          )}
        >
          {positive ? '+' : ''}
          {alt.scoreDelta}
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Hero band                                                           */
/* ------------------------------------------------------------------ */

function HeroBand({ view }: { view: AfterActionViewModelV1 }) {
  const score = view.score;
  const overallPct = Math.round((score.overallScore / score.maxScore) * 100);
  const band = scoreBand(overallPct);

  return (
    <Surface
      data-testid="after-action-overall"
      aria-label="Operation debrief overview"
      className="p-6 lg:p-8"
    >
      <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr] lg:gap-10">
        {/* Verdict — the hero: oversized score numeral + grade */}
        <div className="flex flex-col justify-center gap-4" data-testid="overall-score-block">
          <span className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-accent-cyan)]')}>
            Final score
          </span>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-4">
            <div className="flex items-baseline gap-2">
              <span
                data-testid="overall-score"
                className={cn(
                  'font-[family-name:var(--aegis-font-display)] text-6xl font-semibold leading-none tabular-nums lg:text-8xl',
                  band.text,
                )}
              >
                {score.overallScore.toFixed(1)}
              </span>
              <span className="font-mono text-lg text-[var(--aegis-text-muted)] tabular-nums lg:text-2xl">
                / {score.maxScore}
              </span>
            </div>
            <span
              data-testid="overall-grade"
              className={cn(
                'flex size-16 flex-none items-center justify-center rounded-[var(--aegis-radius-lg)] border font-[family-name:var(--aegis-font-display)] text-4xl font-bold lg:size-20 lg:text-5xl',
                GRADE_CLASS[score.grade],
              )}
            >
              {score.grade}
            </span>
          </div>
          <ScoreMeter
            value={score.overallScore / score.maxScore}
            label="Overall"
            hideValue
            className="max-w-md"
          />
          <div className="flex items-center gap-3">
            <span
              data-testid="overall-passed"
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold',
                score.passed
                  ? 'text-[var(--aegis-status-normal)] border-[var(--aegis-status-normal)]/40 bg-[var(--aegis-status-normal-bg)]'
                  : 'text-[var(--aegis-status-compromised)] border-[var(--aegis-status-compromised)]/40 bg-[var(--aegis-status-compromised-bg)]',
              )}
            >
              {score.passed ? 'Passed' : 'Failed'}
            </span>
            <span className="font-mono text-sm text-[var(--aegis-text-muted)] tabular-nums">
              {overallPct}%
            </span>
          </div>
        </div>

        {/* Identity + provenance — supporting context on a shared surface */}
        <div className="flex flex-col gap-4 border-t border-[var(--aegis-border-subtle)] pt-6 lg:border-l lg:border-t-0 lg:pl-10 lg:pt-0">
          <div className="flex items-center justify-between gap-2">
            <span className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-muted)]')}>
              After-action review
            </span>
            <Badge>{view.runStatus}</Badge>
          </div>
          <h1 className="font-[family-name:var(--aegis-font-display)] text-2xl font-semibold tracking-[0.01em] text-[var(--aegis-text-primary)]">
            Operation debrief
          </h1>
          <div className="flex items-center gap-2">
            <span className="text-[0.7rem] uppercase tracking-[0.06em] text-[var(--aegis-text-muted)]">
              Run
            </span>
            <MonoChip value={view.runId} label="run id" />
          </div>
          {score.hiddenCauseRevealed ? (
            <div
              className="rounded-[var(--aegis-radius-md)] border border-[var(--aegis-status-contained)]/40 bg-[var(--aegis-status-contained-bg)] px-3 py-2"
              data-testid="hidden-cause-reveal"
            >
              <div className="text-[0.65rem] font-semibold uppercase tracking-[0.1em] text-[var(--aegis-status-contained)]">
                Hidden cause revealed
              </div>
              <div className="mt-0.5 text-sm font-medium text-[var(--aegis-text-primary)]">
                {score.hiddenCauseLabel ?? score.hiddenCauseId}
              </div>
            </div>
          ) : null}
          <div className="mt-auto flex flex-col gap-2 pt-1">
            <span className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-faint)]')}>
              Provenance
            </span>
            <div className="flex flex-wrap gap-1.5" data-testid="score-provenance">
              <Pill>scenario {score.provenance.scenarioVersion}</Pill>
              <Pill>rubric {score.provenance.rubricVersion}</Pill>
              <Pill>engine {score.provenance.gradingEngineVersion}</Pill>
              <Pill>
                events {score.provenance.inputEventSequenceFrom}–
                {score.provenance.inputEventSequenceTo}
              </Pill>
            </div>
          </div>
        </div>
      </div>
    </Surface>
  );
}

/* ------------------------------------------------------------------ */
/* Dashboard body                                                      */
/* ------------------------------------------------------------------ */

function DashboardBody({ view }: { view: AfterActionViewModelV1 }) {
  const score = view.score;
  const [selectedCriterionId, setSelectedCriterionId] = useState(
    score.components[0]?.criterionId ?? '',
  );
  const selected = useMemo(
    () =>
      score.components.find((c) => c.criterionId === selectedCriterionId) ?? score.components[0],
    [score.components, selectedCriterionId],
  );
  const selectedExplanation = selected?.explanations[0];

  const handleExport = useCallback(() => {
    try {
      const blob = new Blob([JSON.stringify(view, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `after-action-${view.runId}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      /* download unavailable — ignore */
    }
  }, [view]);

  const noTimeline = view.timelineHighlights.length === 0 && score.decisionReviews.length === 0;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6" data-testid="after-action-dashboard">
      <HeroBand view={view} />

      {/* Score analysis — breakdown and explanation share one surface */}
      <Surface aria-label="Score analysis" className="p-5 lg:p-6">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-8">
          <div className="flex min-w-0 flex-col gap-3">
            <ZoneHeading count={score.components.length}>Score breakdown</ZoneHeading>
            <QuietList data-testid="score-category-list">
              {score.components.map((component) => (
                <ComponentRow
                  key={component.criterionId}
                  component={component}
                  selected={component.criterionId === selected?.criterionId}
                  onSelect={() => {
                    setSelectedCriterionId(component.criterionId);
                  }}
                />
              ))}
            </QuietList>
          </div>
          <div className="flex min-w-0 flex-col gap-3 border-t border-[var(--aegis-border-subtle)] pt-5 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
            <ZoneHeading>Score explanation</ZoneHeading>
            {selected ? (
              <p className="text-sm text-[var(--aegis-text-secondary)]">{selected.label}</p>
            ) : null}
            {selectedExplanation ? (
              <ExplanationPanel explanation={selectedExplanation} runId={view.runId} />
            ) : (
              <EmptyState
                title="No explanation"
                description="Select a score category to inspect its grounding."
              />
            )}
          </div>
        </div>
      </Surface>

      {/* Investigation — timeline (wide) + evidence coverage (narrow) */}
      <div className="grid gap-5 lg:grid-cols-12 lg:gap-6">
        <Surface aria-label="Timeline and decisions" className="p-5 lg:col-span-7 lg:p-6">
          <div className="flex flex-col gap-3">
            <ZoneHeading count={view.timelineHighlights.length + score.decisionReviews.length}>
              Timeline &amp; decisions
            </ZoneHeading>
            <QuietList data-testid="timeline-review">
              {noTimeline ? (
                <p className="py-2 text-sm text-[var(--aegis-text-muted)]">
                  No recorded decisions.
                </p>
              ) : null}
              {view.timelineHighlights.map((item) => (
                <TimelineRow
                  key={`${item.kind}-${String(item.sequence)}-${item.label}`}
                  item={item}
                  runId={view.runId}
                />
              ))}
              {score.decisionReviews.map((review) => (
                <DecisionRow key={review.decisionId} review={review} />
              ))}
            </QuietList>
          </div>
        </Surface>
        <Surface aria-label="Evidence coverage" className="p-5 lg:col-span-5 lg:p-6">
          <div className="flex flex-col gap-3">
            <ZoneHeading count={score.missedEvidence.length}>Evidence coverage</ZoneHeading>
            <div data-testid="missed-evidence-list">
              {score.missedEvidence.length === 0 ? (
                <div className="flex items-center gap-2 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-status-normal)]/30 bg-[var(--aegis-status-normal-bg)] px-3 py-2.5 text-sm text-[var(--aegis-status-normal)]">
                  All expected evidence for the true cause was surfaced.
                </div>
              ) : (
                <QuietList>
                  {score.missedEvidence.map((item) => (
                    <MissedEvidenceRow key={item.expectedEvidenceKey} item={item} />
                  ))}
                </QuietList>
              )}
            </div>
          </div>
        </Surface>
      </div>

      {/* Learning — alternatives (narrow) + debrief/export (wide) */}
      <div className="grid gap-5 lg:grid-cols-12 lg:gap-6">
        <Surface aria-label="Valid alternatives" className="p-5 lg:col-span-5 lg:p-6">
          <div className="flex flex-col gap-3">
            <ZoneHeading count={score.validAlternatives.length}>Valid alternatives</ZoneHeading>
            <p className="text-xs text-[var(--aegis-text-muted)]">
              Counterfactual branches · not facts of this run
            </p>
            <div data-testid="valid-alternatives-list">
              {score.validAlternatives.length === 0 ? (
                <p className="py-2 text-sm text-[var(--aegis-text-muted)]">
                  No alternative response branches identified.
                </p>
              ) : (
                <QuietList>
                  {score.validAlternatives.map((alt) => (
                    <AlternativeRow key={alt.alternativeId} alt={alt} />
                  ))}
                </QuietList>
              )}
            </div>
          </div>
        </Surface>
        <Surface aria-label="Debrief, lessons and export" className="p-5 lg:col-span-7 lg:p-6">
          <div className="flex flex-col gap-5 text-sm" data-testid="scribe-integration">
            <div className="flex flex-col gap-3">
              <ZoneHeading>Debrief &amp; export</ZoneHeading>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  {view.scribeReportId ? (
                    <>
                      <MonoChip value={view.scribeReportId} label="SCRIBE report id" />
                      {view.scribeVersionNumber != null ? (
                        <Badge>{`v${String(view.scribeVersionNumber)}`}</Badge>
                      ) : null}
                    </>
                  ) : (
                    <span className="text-[var(--aegis-text-muted)]">No SCRIBE report linked.</span>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button asChild size="sm" variant="outline" data-testid="open-scribe-report">
                    <Link href="/reports">Open SCRIBE report</Link>
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={handleExport}
                    data-testid="export-json"
                  >
                    Export JSON
                  </Button>
                </div>
              </div>
            </div>

            {view.lessons.length > 0 ? (
              <div className="flex flex-col gap-2">
                <SectionLabel count={view.lessons.length}>Lessons</SectionLabel>
                <ul className="space-y-1.5" data-testid="lessons-list">
                  {view.lessons.map((lesson) => (
                    <li
                      key={lesson}
                      className="flex gap-2 text-sm leading-5 text-[var(--aegis-text-secondary)]"
                    >
                      <span className="mt-2 size-1 flex-none rounded-full bg-[var(--aegis-accent-cyan)]" />
                      {lesson}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="flex flex-col gap-2">
              <SectionLabel>Integrity</SectionLabel>
              <div
                className="rounded-[var(--aegis-radius-md)] bg-[var(--aegis-surface-raised)] px-3 py-1.5"
                data-testid="export-metadata"
              >
                <MetaRow label="Integrity">
                  <MonoChip
                    value={score.provenance.integrityChecksum}
                    label="integrity checksum"
                    variant="checksum"
                  />
                </MetaRow>
                <MetaRow label="Fingerprint">
                  <MonoChip
                    value={score.provenance.fingerprint}
                    label="fingerprint"
                    variant="checksum"
                  />
                </MetaRow>
                <MetaRow label="Input checksum">
                  <MonoChip
                    value={score.provenance.inputChecksum}
                    label="input checksum"
                    variant="checksum"
                  />
                </MetaRow>
                <MetaRow label="Calculated">
                  <span
                    className="font-mono text-[0.7rem] text-[var(--aegis-text-secondary)]"
                    title={score.provenance.calculatedAt}
                  >
                    {score.provenance.calculatedAt}
                  </span>
                </MetaRow>
              </div>
            </div>

            {score.coachingText ? (
              <div
                className="rounded-[var(--aegis-radius-md)] border-l-2 border-l-[var(--aegis-accent-line)] bg-[var(--aegis-surface-raised)]/60 px-3 py-2.5"
                data-testid="coaching-text"
              >
                <div className="text-[0.65rem] font-semibold uppercase tracking-[0.1em] text-[var(--aegis-text-muted)]">
                  Coaching (non-authoritative)
                </div>
                <p className="mt-1 text-sm leading-6 text-[var(--aegis-text-secondary)]">
                  {score.coachingText}
                </p>
              </div>
            ) : null}
          </div>
        </Surface>
      </div>
    </div>
  );
}

export interface AfterActionDashboardProps {
  runId: string;
}

function ScoreSection({ runId }: AfterActionDashboardProps) {
  const query = useAfterActionView(runId);

  if (query.isLoading) {
    return <LoadingState message="Loading after-action review" />;
  }

  if (query.isError) {
    const error = query.error;
    const message =
      error instanceof ApiClientError
        ? `${error.code}: ${error.message}`
        : 'Failed to load after-action review';
    return (
      <EmptyState
        title="After-action unavailable"
        description={message}
        data-testid="after-action-error"
      />
    );
  }

  if (!query.data) {
    return (
      <EmptyState
        title="No after-action data"
        description="Score this completed run to begin review."
        data-testid="after-action-empty"
      />
    );
  }

  return <DashboardBody view={query.data} />;
}

export function AfterActionDashboard({ runId }: AfterActionDashboardProps) {
  // The score section and the adversary dossier are independently gated: the dossier
  // self-gates on terminal run status (rendering a sealed state mid-run) so it appears even
  // before a completed run has been scored, while the score section renders whatever the
  // after-action query returns.
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <ScoreSection runId={runId} />
      <AdversaryDossier runId={runId} />
    </div>
  );
}

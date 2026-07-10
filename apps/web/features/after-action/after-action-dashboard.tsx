'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

import type {
  AfterActionViewModelV1,
  DecisionReviewV1,
  MissedEvidenceItemV1,
  ScoreComponentV1,
  ScoreExplanationV1,
  ValidAlternativeV1,
} from '@aegis/contracts-ts';
import { Badge, Button, EmptyState, LoadingState, Panel } from '@aegis/ui';

import { useAfterActionView } from '@/features/after-action/use-after-action-queries';
import { ApiClientError } from '@/lib/api/types';

export interface AfterActionDashboardProps {
  runId: string;
}

function ComponentRow({
  component,
  selected,
  onSelect,
}: {
  component: ScoreComponentV1;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      data-testid={`score-component-${component.criterionId}`}
      className={`w-full rounded-[var(--aegis-radius-sm)] border px-3 py-2 text-left transition ${
        selected
          ? 'border-[var(--aegis-accent)] bg-[var(--aegis-surface-elevated)]'
          : 'border-[var(--aegis-border-subtle)]'
      }`}
      onClick={onSelect}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{component.label}</span>
        <Badge>{Math.round(component.rawScore * 100)}%</Badge>
      </div>
      <div className="mt-1 text-xs text-[var(--aegis-text-secondary)]">
        weight {component.weight.toFixed(2)} · contribution{' '}
        {component.weightedContribution.toFixed(1)}
      </div>
    </button>
  );
}

function ExplanationPanel({ explanation }: { explanation: ScoreExplanationV1 }) {
  return (
    <div data-testid="score-explanation" className="space-y-2 text-sm">
      <div>
        <span className="font-medium">Rule ID:</span>{' '}
        <code data-testid="score-rule-id">{explanation.ruleId}</code>
      </div>
      <p>{explanation.reason}</p>
      {explanation.eventIds.length > 0 ? (
        <p className="text-xs text-[var(--aegis-text-secondary)]">
          Events: {explanation.eventIds.join(', ')}
        </p>
      ) : null}
      {explanation.evidenceIds.length > 0 ? (
        <p className="text-xs text-[var(--aegis-text-secondary)]">
          Evidence: {explanation.evidenceIds.join(', ')}
        </p>
      ) : null}
      {explanation.sequence != null ? (
        <p className="text-xs text-[var(--aegis-text-secondary)]">
          Sequence: {explanation.sequence}
        </p>
      ) : null}
    </div>
  );
}

function DecisionRow({ review }: { review: DecisionReviewV1 }) {
  return (
    <div
      data-testid={`decision-review-${review.decisionId}`}
      className="rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] px-3 py-2"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{review.kind}</Badge>
        <Badge>{review.outcome}</Badge>
        <span className="text-xs text-[var(--aegis-text-secondary)]">seq {review.sequence}</span>
      </div>
      <p className="mt-2 text-sm">
        Operator <strong>{review.operatorAction}</strong>
        {review.agentRecommendation ? (
          <>
            {' '}
            vs agent recommendation: <em>{review.agentRecommendation}</em>
          </>
        ) : null}
      </p>
      <p className="mt-1 text-xs text-[var(--aegis-text-secondary)]">
        {review.availableInfoSummary}
      </p>
      <p className="mt-1 text-xs">Future knowledge used: {String(review.usedFutureKnowledge)}</p>
    </div>
  );
}

function MissedEvidenceRow({ item }: { item: MissedEvidenceItemV1 }) {
  return (
    <div
      data-testid={`missed-evidence-${item.expectedEvidenceKey}`}
      className="rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] px-3 py-2 text-sm"
    >
      <div className="font-medium">{item.expectedEvidenceKey}</div>
      <p className="text-xs text-[var(--aegis-text-secondary)]">{item.description}</p>
      <p className="mt-1 text-xs">
        {item.eventType}
        {item.assetId ? ` · ${item.assetId}` : ''}
        {item.bookmarkSequence != null ? ` · seq ${String(item.bookmarkSequence)}` : ''}
      </p>
    </div>
  );
}

function AlternativeRow({ alt }: { alt: ValidAlternativeV1 }) {
  return (
    <div
      data-testid={`valid-alternative-${alt.alternativeId}`}
      className="rounded-[var(--aegis-radius-sm)] border border-dashed border-[var(--aegis-border-default)] px-3 py-2"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge data-testid="counterfactual-label">non-authoritative</Badge>
        <Badge>{alt.kind}</Badge>
      </div>
      <p className="mt-2 text-sm font-medium">{alt.label}</p>
      <p className="mt-1 text-xs text-[var(--aegis-text-secondary)]">{alt.description}</p>
      <p className="mt-1 text-xs">
        Projected score {alt.projectedOverallScore} (delta {alt.scoreDelta > 0 ? '+' : ''}
        {alt.scoreDelta})
      </p>
    </div>
  );
}

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

  return (
    <div className="space-y-4" data-testid="after-action-dashboard">
      <Panel data-testid="after-action-overall">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold">After-action review</h1>
            <p className="text-sm text-[var(--aegis-text-secondary)]">
              Completed run {view.runId} · status {view.runStatus}
            </p>
          </div>
          <div className="text-right" data-testid="overall-score-block">
            <div className="text-3xl font-semibold" data-testid="overall-score">
              {score.overallScore.toFixed(1)}
              <span className="text-base text-[var(--aegis-text-secondary)]">
                {' '}
                / {score.maxScore}
              </span>
            </div>
            <div className="mt-1 flex justify-end gap-2">
              <Badge data-testid="overall-grade">Grade {score.grade}</Badge>
              <Badge data-testid="overall-passed">{score.passed ? 'Passed' : 'Failed'}</Badge>
            </div>
          </div>
        </div>
        {score.hiddenCauseRevealed ? (
          <div
            className="mt-3 rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] px-3 py-2"
            data-testid="hidden-cause-reveal"
          >
            <div className="text-xs uppercase tracking-wide text-[var(--aegis-text-secondary)]">
              Hidden cause (post-completion reveal)
            </div>
            <div className="text-sm font-medium">
              {score.hiddenCauseLabel ?? score.hiddenCauseId}
            </div>
          </div>
        ) : null}
        <div
          className="mt-3 flex flex-wrap gap-2 text-xs text-[var(--aegis-text-secondary)]"
          data-testid="score-provenance"
        >
          <span>scenario {score.provenance.scenarioVersion}</span>
          <span>rubric {score.provenance.rubricVersion}</span>
          <span>engine {score.provenance.gradingEngineVersion}</span>
          <span>
            events {score.provenance.inputEventSequenceFrom}–{score.provenance.inputEventSequenceTo}
          </span>
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <h2 className="mb-2 text-sm font-semibold">Score categories</h2>
          <div className="space-y-2" data-testid="score-category-list">
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
          </div>
        </Panel>
        <Panel>
          <h2 className="mb-2 text-sm font-semibold">Score explanation</h2>
          {selectedExplanation ? (
            <ExplanationPanel explanation={selectedExplanation} />
          ) : (
            <EmptyState title="No explanation" description="Select a score category." />
          )}
          {selectedExplanation?.sequence != null ? (
            <div className="mt-3">
              <Button asChild size="sm" data-testid="jump-to-replay">
                <Link
                  href={`/replay/${view.runId}?sequence=${String(selectedExplanation.sequence)}`}
                >
                  Jump to replay seq {selectedExplanation.sequence}
                </Link>
              </Button>
            </div>
          ) : null}
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <h2 className="mb-2 text-sm font-semibold">Timeline / decisions</h2>
          <div className="space-y-2" data-testid="timeline-review">
            {view.timelineHighlights.map((item) => (
              <div
                key={`${item.kind}-${String(item.sequence)}-${item.label}`}
                className="rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] px-3 py-2 text-sm"
                data-testid={`timeline-highlight-${String(item.sequence)}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span>{item.label}</span>
                  <span className="text-xs text-[var(--aegis-text-secondary)]">
                    seq {item.sequence}
                  </span>
                </div>
                <Button asChild size="sm" variant="ghost" className="mt-1 px-0">
                  <Link href={`/replay/${view.runId}?sequence=${String(item.sequence)}`}>
                    Open in replay
                  </Link>
                </Button>
              </div>
            ))}
            {score.decisionReviews.map((review) => (
              <DecisionRow key={review.decisionId} review={review} />
            ))}
          </div>
        </Panel>
        <Panel>
          <h2 className="mb-2 text-sm font-semibold">Evidence coverage</h2>
          <div className="space-y-2" data-testid="missed-evidence-list">
            {score.missedEvidence.length === 0 ? (
              <p className="text-sm text-[var(--aegis-text-secondary)]">
                No missed expected evidence for the true cause.
              </p>
            ) : (
              score.missedEvidence.map((item) => (
                <MissedEvidenceRow key={item.expectedEvidenceKey} item={item} />
              ))
            )}
          </div>
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <h2 className="mb-2 text-sm font-semibold">
            Valid alternatives{' '}
            <span className="font-normal text-[var(--aegis-text-secondary)]">
              (counterfactual · not run facts)
            </span>
          </h2>
          <div className="space-y-2" data-testid="valid-alternatives-list">
            {score.validAlternatives.map((alt) => (
              <AlternativeRow key={alt.alternativeId} alt={alt} />
            ))}
          </div>
        </Panel>
        <Panel>
          <h2 className="mb-2 text-sm font-semibold">SCRIBE / lessons / export</h2>
          <div className="space-y-2 text-sm" data-testid="scribe-integration">
            {view.scribeReportId ? (
              <p>
                SCRIBE report <code>{view.scribeReportId}</code>
                {view.scribeVersionNumber != null ? ` · v${String(view.scribeVersionNumber)}` : ''}
              </p>
            ) : (
              <p className="text-[var(--aegis-text-secondary)]">No SCRIBE report linked.</p>
            )}
            <Button asChild size="sm" variant="outline" data-testid="open-scribe-report">
              <Link href="/reports">Open SCRIBE report</Link>
            </Button>
            <ul className="list-disc space-y-1 pl-5" data-testid="lessons-list">
              {view.lessons.map((lesson) => (
                <li key={lesson}>{lesson}</li>
              ))}
            </ul>
            <div
              className="rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] px-3 py-2 text-xs"
              data-testid="export-metadata"
            >
              <div>Integrity: {score.provenance.integrityChecksum}</div>
              <div>Fingerprint: {score.provenance.fingerprint}</div>
              <div>Input checksum: {score.provenance.inputChecksum}</div>
              <div>Calculated at: {score.provenance.calculatedAt}</div>
            </div>
            {score.coachingText ? (
              <div
                className="rounded-[var(--aegis-radius-sm)] border border-dashed border-[var(--aegis-border-default)] px-3 py-2"
                data-testid="coaching-text"
              >
                <div className="text-xs uppercase tracking-wide text-[var(--aegis-text-secondary)]">
                  Coaching (non-authoritative)
                </div>
                <p className="mt-1">{score.coachingText}</p>
              </div>
            ) : null}
          </div>
        </Panel>
      </div>
    </div>
  );
}

export function AfterActionDashboard({ runId }: AfterActionDashboardProps) {
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

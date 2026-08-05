'use client';

import { useMemo, useState } from 'react';

import {
  NodeStatus,
  type AlertV1,
  type GraphSnapshotV1,
  type IncidentV1,
} from '@aegis/contracts-ts';
import { Panel, cn, getNodeStatusPresentation } from '@aegis/ui';

import { ACTIVITY_COPY, useRunActivity, type ActivityLevel } from '@/features/live-run';
import { useFocusAsset } from '@/features/operational-graph';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

import {
  LIFECYCLE_LABEL,
  buildAlertCards,
  readReveals,
  readStatusTransitions,
  simClock,
  type AlertCard,
  type AlertLifecycle,
  type AssetFacts,
  type RevealNote,
} from './alert-model';

const SEVERITY_ACCENT: Record<string, string> = {
  critical: 'var(--aegis-risk-critical)',
  high: 'var(--aegis-risk-high)',
  medium: 'var(--aegis-risk-medium)',
  low: 'var(--aegis-risk-low)',
};

function severityAccent(severity: string): string {
  return SEVERITY_ACCENT[severity.toLowerCase()] ?? 'var(--aegis-risk-medium)';
}

const KNOWN_STATUSES = new Set<string>(Object.values(NodeStatus));

const LIFECYCLE_TONE: Record<AlertLifecycle, string> = {
  new: 'border-[var(--aegis-accent-line)] text-[var(--aegis-accent-strong)]',
  investigated: 'border-[var(--aegis-border-default)] text-[var(--aegis-text-secondary)]',
  superseded: 'border-[var(--aegis-border-subtle)] text-[var(--aegis-text-muted)]',
  escalated:
    'border-[color-mix(in_srgb,var(--aegis-risk-high)_60%,transparent)] text-[var(--aegis-risk-high)]',
};

const ACTIVITY_TONE: Record<ActivityLevel, string> = {
  quiet: 'var(--aegis-text-muted)',
  elevated: 'var(--aegis-risk-medium)',
  active: 'var(--aegis-risk-high)',
};

/** Small uppercase mono chip — the panel's utility voice. */
function Chip({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        'rounded-full border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide',
        className,
      )}
    >
      {children}
    </span>
  );
}

/**
 * The run's observable cadence, held permanently above the alert list.
 *
 * Under fog of war the graph can sit still for minutes while the attacker works, and the
 * operator has no way to tell that apart from an idle run. This says which it is, at a
 * glance, without naming anything the fog is hiding: a twelve-bucket bar of recent weighted
 * event pressure plus one word. Bar heights change on their own, so the level is legible
 * without motion; there is no animation to suppress.
 */
function ActivityStrip() {
  const activity = useRunActivity();
  const copy = ACTIVITY_COPY[activity.level];
  const peak = Math.max(1, ...activity.buckets);
  const tone = ACTIVITY_TONE[activity.level];

  return (
    <div
      className="flex items-center gap-3 border-b border-[var(--aegis-border-subtle)] pb-3"
      data-testid="activity-strip"
      data-level={activity.level}
    >
      <div
        className="flex h-6 min-w-0 flex-1 items-end gap-[2px]"
        role="img"
        aria-label={`Run activity: ${copy.label.toLowerCase()}. ${String(activity.count)} events in the last ${String(activity.windowSeconds)} seconds of simulated time.`}
      >
        {activity.buckets.map((value, index) => (
          <span
            key={index}
            className="min-w-0 flex-1 rounded-[1px] transition-[height,background-color] duration-500"
            style={{
              height: `${String(Math.max(8, Math.round((value / peak) * 100)))}%`,
              backgroundColor: value > 0 ? tone : 'var(--aegis-border-subtle)',
              opacity: value > 0 ? 1 : 0.5,
            }}
          />
        ))}
      </div>
      <div className="flex shrink-0 flex-col items-end">
        <span
          className="font-[family-name:var(--aegis-font-display)] text-[0.6875rem] font-semibold uppercase tracking-[0.14em]"
          style={{ color: tone }}
        >
          {copy.label}
        </span>
        <span className="font-mono text-[9px] tabular-nums text-[var(--aegis-text-muted)]">
          {activity.count} in {activity.windowSeconds}s
        </span>
      </div>
      <span className="sr-only" role="status">
        {copy.detail}
      </span>
    </div>
  );
}

/** The durable, explained hidden-condition reveal. */
function RevealCard({ note, sole }: { note: RevealNote; sole: boolean }) {
  return (
    <li
      className="rounded-[var(--aegis-radius-md)] border border-[color-mix(in_srgb,var(--aegis-risk-critical)_55%,transparent)] bg-[color-mix(in_srgb,var(--aegis-risk-critical)_10%,var(--aegis-surface-elevated))] px-3 py-3"
      data-testid={`alert-reveal-${String(note.sequence)}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-[var(--aegis-radius-sm)] bg-[var(--aegis-risk-critical)] px-1.5 py-0.5 font-[family-name:var(--aegis-font-display)] text-[9px] font-bold uppercase tracking-[0.14em] text-[var(--aegis-surface-base)]">
          Cause revealed
        </span>
        <span className="ml-auto font-mono text-[10px] tabular-nums text-[var(--aegis-text-muted)]">
          {simClock(note.simTime)} · SEQ {note.sequence}
        </span>
      </div>
      <p className="mt-2 text-sm font-medium leading-5 text-[var(--aegis-text-primary)]">
        {note.cause}
      </p>
      <p className="mt-1.5 text-xs leading-5 text-[var(--aegis-text-secondary)]">
        {/* Only claim to be *the* cause when it is the only one on the board. With several
            revealed, each card saying "this is what was driving it" is four contradictions. */}
        {sole
          ? 'This is what was driving the activity you have been chasing.'
          : 'The most recent cause the scenario stopped hiding.'}{' '}
        {note.assetLabels.length > 0
          ? `It moved ${note.assetLabels.join(', ')}.`
          : 'The board now shows what the fog was holding back.'}
      </p>
    </li>
  );
}

/**
 * The reveals on the board: the newest cause in full, everything revealed before it behind
 * one line. Four equally loud cards each announcing itself as the cause is four claims the
 * operator has to reconcile; one card and a count is the same information, ranked.
 */
function Reveals({ notes }: { notes: RevealNote[] }) {
  const [showEarlier, setShowEarlier] = useState(false);
  const [newest, ...earlier] = notes;
  if (!newest) {
    return null;
  }
  return (
    <>
      <RevealCard note={newest} sole={earlier.length === 0} />
      {earlier.length > 0 ? (
        <li
          className="rounded-[var(--aegis-radius-md)] border border-dashed border-[color-mix(in_srgb,var(--aegis-risk-critical)_35%,transparent)] px-3 py-2"
          data-testid="alert-reveals-earlier"
        >
          <button
            type="button"
            onClick={() => {
              setShowEarlier((open) => !open);
            }}
            aria-expanded={showEarlier}
            className="flex w-full items-center gap-2 text-left text-xs text-[var(--aegis-text-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--aegis-focus-ring)]"
          >
            <span aria-hidden="true" className="font-mono text-[10px]">
              {showEarlier ? '▾' : '▸'}
            </span>
            {earlier.length === 1
              ? '1 earlier cause revealed'
              : `${String(earlier.length)} earlier causes revealed`}
          </button>
          {showEarlier ? (
            <ul className="mt-2 flex flex-col gap-1 border-t border-[var(--aegis-border-subtle)] pt-2">
              {earlier.map((note) => (
                <li
                  key={note.key}
                  data-testid={`alert-reveal-earlier-${String(note.sequence)}`}
                  className="flex items-baseline gap-2 text-[11px] text-[var(--aegis-text-secondary)]"
                >
                  <span className="shrink-0 font-mono tabular-nums text-[var(--aegis-text-muted)]">
                    {simClock(note.simTime)}
                  </span>
                  <span className="min-w-0">{note.cause}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </li>
      ) : null}
    </>
  );
}

function StatusChip({ status }: { status: string }) {
  if (!KNOWN_STATUSES.has(status)) {
    return null;
  }
  const presentation = getNodeStatusPresentation(
    status as (typeof NodeStatus)[keyof typeof NodeStatus],
  );
  return (
    <span
      className={cn(
        'rounded-full px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide',
        presentation.tokenClass,
      )}
      aria-label={presentation.ariaLabel}
    >
      {presentation.label}
    </span>
  );
}

interface AlertCardViewProps {
  card: AlertCard;
  onOpen: (key: string) => void;
  /** Fired when the operator opens either account of why the alert fired. */
  onExplanationOpened: () => void;
  onFocusAsset: (assetId: string) => void;
  onOpenIncident: (incidentId: string) => void;
}

/**
 * One alert, told as two beats: what the detector saw, and what became of the asset it
 * named. The consequence line is the point of the card — an operator scanning the rail
 * should be able to see that the alert they ignored is the one that turned compromised,
 * without opening anything.
 */
function AlertCardView({
  card,
  onOpen,
  onExplanationOpened,
  onFocusAsset,
  onOpenIncident,
}: AlertCardViewProps) {
  const accent = severityAccent(card.alert.severity);

  // `toggle` fires in both directions; only opening is an operator reading the account.
  // Collapsing must not retract either signal — having read it once is the durable fact.
  const handleDisclosureToggle = (event: React.SyntheticEvent<HTMLDetailsElement>) => {
    if (!event.currentTarget.open) {
      return;
    }
    onOpen(card.key);
    onExplanationOpened();
  };

  return (
    <li
      className="rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] border-l-[3px] bg-[var(--aegis-surface-elevated)] px-3 py-3 text-sm shadow-[var(--aegis-shadow-control)]"
      style={{ borderLeftColor: accent }}
      data-testid={`alert-item-${card.alert.id}`}
      data-lifecycle={card.lifecycle}
    >
      <div className="flex items-start gap-2">
        <p className="min-w-0 flex-1 font-medium leading-5 text-[var(--aegis-text-primary)]">
          {card.alert.title}
        </p>
        {card.count > 1 ? (
          <span
            className="shrink-0 rounded-full border border-[var(--aegis-border-default)] px-1.5 py-0.5 font-mono text-[10px] tabular-nums text-[var(--aegis-text-secondary)]"
            data-testid={`alert-repeat-${card.alert.id}`}
            title={`Seen ${String(card.count)} times, last at ${simClock(card.lastSimTime)}`}
          >
            ×{card.count}
          </span>
        ) : null}
      </div>

      <div className="mt-1.5 flex flex-wrap items-center gap-2">
        <button
          type="button"
          data-testid={`alert-asset-${card.alert.id}`}
          onClick={() => {
            onOpen(card.key);
            onFocusAsset(card.assetId);
          }}
          className="rounded-[var(--aegis-radius-sm)] text-[0.8125rem] font-medium text-[var(--aegis-accent-strong)] underline decoration-[var(--aegis-accent-line)] underline-offset-2 transition-colors hover:text-[var(--aegis-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--aegis-focus-ring)]"
        >
          {card.assetLabel}
        </button>
        {card.assetStatus ? <StatusChip status={card.assetStatus} /> : null}
      </div>

      <p className="mt-2 text-xs leading-5 text-[var(--aegis-text-secondary)]">
        {card.whyItMatters}
      </p>

      {card.outcome ? (
        <p
          className="mt-2 border-l border-[var(--aegis-border-strong)] pl-2 font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]"
          data-testid={`alert-outcome-${card.alert.id}`}
        >
          Then → {card.outcome.status.replace(/_/g, ' ')} · {simClock(card.outcome.simTime)} · SEQ{' '}
          {card.outcome.sequence}
        </p>
      ) : null}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Chip className={LIFECYCLE_TONE[card.lifecycle]}>{LIFECYCLE_LABEL[card.lifecycle]}</Chip>
        <span className="font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
          {card.alert.severity}
        </span>
        {card.alert.confidence != null ? (
          <span className="font-mono text-[10px] tabular-nums text-[var(--aegis-text-muted)]">
            {Math.round(card.alert.confidence * 100)}%
          </span>
        ) : null}
        {card.lastSequence !== null ? (
          <span className="font-mono text-[10px] tabular-nums text-[var(--aegis-text-muted)]">
            SEQ{' '}
            {card.firstSequence !== null && card.firstSequence !== card.lastSequence
              ? `${String(card.firstSequence)}–${String(card.lastSequence)}`
              : String(card.lastSequence)}{' '}
            · {simClock(card.lastSimTime)}
          </span>
        ) : null}
      </div>

      {card.incident ? (
        <button
          type="button"
          data-testid={`alert-incident-${card.alert.id}`}
          onClick={() => {
            onOpenIncident(card.incident?.id ?? '');
          }}
          className="mt-2 block w-full rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] px-2 py-1 text-left text-[11px] text-[var(--aegis-text-secondary)] transition-colors hover:border-[var(--aegis-border-strong)] hover:text-[var(--aegis-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--aegis-focus-ring)]"
        >
          Open case · {card.incident.title}
        </button>
      ) : null}

      {/*
        Two accounts of the same firing, in the order an operator needs them: the detector's
        reasoning in plain language first, and the rule arithmetic demoted to a labelled
        aside inside it. The anomaly model gets its own disclosure rather than sharing this
        one — it answers a different question ("how far outside normal?") and only ML alerts
        carry it. Both are closed by default; the card's own stakes line is what the operator
        reads while scanning, and nothing here should compete with it.
      */}
      {(card.alert.explanation ?? card.detectorDetail) ? (
        <details className="mt-2" onToggle={handleDisclosureToggle}>
          <summary
            className="cursor-pointer font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]"
            data-testid={`alert-explanation-${card.alert.id}`}
          >
            Explanation
          </summary>
          {card.alert.explanation ? (
            <p className="mt-1.5 break-words text-xs leading-5 text-[var(--aegis-text-secondary)]">
              {card.alert.explanation.summary}
            </p>
          ) : null}
          {card.detectorDetail ? (
            <p className="mt-1.5 break-words font-mono text-[10px] leading-4 text-[var(--aegis-text-muted)]">
              <span className="uppercase tracking-wide text-[var(--aegis-text-muted)]">
                Detector detail
              </span>
              <br />
              {card.detectorDetail}
            </p>
          ) : null}
          {card.alert.detectorVersion ? (
            <p className="mt-1.5 font-mono text-[10px] leading-4 text-[var(--aegis-text-muted)]">
              {card.alert.detectorId ?? 'detector'} {card.alert.detectorVersion}
            </p>
          ) : null}
        </details>
      ) : null}

      {card.anomaly ? (
        <details className="mt-1.5" onToggle={handleDisclosureToggle}>
          <summary
            className="cursor-pointer font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]"
            data-testid={`alert-anomaly-${card.alert.id}`}
          >
            Anomaly model
          </summary>
          {card.anomaly.summary ? (
            <p className="mt-1.5 break-words text-xs leading-5 text-[var(--aegis-text-secondary)]">
              {card.anomaly.summary}
            </p>
          ) : null}
          {card.anomaly.observedScore !== null ? (
            <p className="mt-1.5 font-mono text-[10px] tabular-nums leading-4 text-[var(--aegis-text-muted)]">
              Score {card.anomaly.observedScore.toFixed(2)}
              {card.anomaly.threshold !== null
                ? ` · threshold ${card.anomaly.threshold.toFixed(2)}`
                : ''}
            </p>
          ) : null}
          {card.anomaly.topFeatures.length > 0 ? (
            <p className="mt-1.5 break-words text-[10px] leading-4 text-[var(--aegis-text-muted)]">
              Top features: {card.anomaly.topFeatures.join(', ')}
            </p>
          ) : null}
          {card.anomaly.modelVersionId ? (
            <p className="mt-1.5 break-words font-mono text-[10px] leading-4 text-[var(--aegis-text-muted)]">
              {card.anomaly.modelVersionId}
            </p>
          ) : null}
        </details>
      ) : null}
    </li>
  );
}

export interface AlertsPanelProps {
  alerts: AlertV1[];
  incidents: IncidentV1[];
  snapshot: GraphSnapshotV1 | null;
  /** Live timeline entries, used for status transitions and reveals. */
  timelineEntries?: readonly {
    eventType: string;
    label: string;
    sequence: number;
    timestamp: string;
  }[];
}

/**
 * The alerts rail.
 *
 * Every card names the asset it is about by its display name and hands the operator to that
 * node on click; exact repeats fold into one card with a count; and each card carries its
 * own lifecycle — new, investigated, superseded, escalated — plus the status transition it
 * preceded. The detector's rule text is still there, one disclosure down, where it belongs
 * for auditing rather than triage.
 */
export function AlertsPanel({ alerts, incidents, snapshot, timelineEntries }: AlertsPanelProps) {
  const focusAsset = useFocusAsset();
  const setSelectedIncidentId = useWorkspaceUiStore((state) => state.setSelectedIncidentId);
  // The guided walkthrough's "read the explanation" objective completes on this flag rather
  // than on an alert merely existing, so opening a card's account has to report it.
  const setAlertExplanationOpened = useWorkspaceUiStore((state) => state.setAlertExplanationOpened);
  const [openedKeys, setOpenedKeys] = useState<ReadonlySet<string>>(() => new Set<string>());

  const assets = useMemo(() => {
    const map = new Map<string, AssetFacts>();
    for (const node of snapshot?.nodes ?? []) {
      map.set(node.id, { label: node.label, status: node.status });
    }
    return map;
  }, [snapshot]);

  const entries = useMemo(() => timelineEntries ?? [], [timelineEntries]);
  const transitions = useMemo(() => readStatusTransitions(entries), [entries]);
  const reveals = useMemo(() => readReveals(entries, assets), [entries, assets]);

  const cards = useMemo(
    () => buildAlertCards({ alerts, incidents, assets, transitions, openedKeys }),
    [alerts, incidents, assets, transitions, openedKeys],
  );

  if (cards.length === 0 && reveals.length === 0) {
    return null;
  }

  return (
    <Panel title="Alerts" density="compact" data-testid="alerts-panel">
      <div className="flex flex-col gap-3">
        <ActivityStrip />
        <ul className="flex flex-col gap-2" data-tutorial-id="alerts-list">
          <Reveals notes={reveals} />
          {cards.map((card) => (
            <AlertCardView
              key={card.key}
              card={card}
              onOpen={(key) => {
                setOpenedKeys((current) =>
                  current.has(key) ? current : new Set([...current, key]),
                );
              }}
              onExplanationOpened={() => {
                setAlertExplanationOpened(true);
              }}
              onFocusAsset={focusAsset}
              onOpenIncident={setSelectedIncidentId}
            />
          ))}
        </ul>
      </div>
    </Panel>
  );
}

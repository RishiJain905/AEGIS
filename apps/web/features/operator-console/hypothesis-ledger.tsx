'use client';

import { useState } from 'react';

import { Alert, Badge, Button, EmptyState } from '@aegis/ui';

import { useCreateHypothesis, useHypothesisLedger } from './use-hypothesis-ledger';
import type { LedgerCard } from './ledger-model';

function parseAssetIds(raw: string): string[] {
  return raw
    .split(',')
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
}

function LedgerCardView({ card }: { card: LedgerCard }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <li
      className={
        card.challenged
          ? 'flex flex-col gap-1.5 rounded-[var(--aegis-radius-md)] border border-[color-mix(in_srgb,var(--aegis-risk-medium)_60%,transparent)] bg-[color-mix(in_srgb,var(--aegis-risk-medium)_9%,var(--aegis-surface-raised))] px-3 py-2'
          : 'flex flex-col gap-1.5 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-3 py-2'
      }
      data-testid={card.challenged ? 'hypothesis-card-challenged' : 'hypothesis-card'}
    >
      <div className="flex items-start gap-2">
        <p className="flex-1 text-[0.8125rem] leading-5 text-[var(--aegis-text-primary)]">
          {card.statement}
        </p>
        <Badge variant="outline" className="shrink-0 text-[9px]">
          {card.origin === 'operator' ? 'Operator' : 'ORACLE'}
        </Badge>
      </div>

      {card.challenged ? (
        <div className="flex flex-col gap-1">
          <button
            type="button"
            onClick={() => {
              setExpanded((v) => !v);
            }}
            aria-expanded={expanded}
            className="flex items-center gap-1.5 text-left"
            data-testid="hypothesis-challenge-badge"
          >
            <span className="rounded-[var(--aegis-radius-sm)] bg-[var(--aegis-risk-medium)] px-1.5 py-0.5 font-[family-name:var(--aegis-font-display)] text-[9px] font-bold uppercase tracking-[0.14em] text-[var(--aegis-surface-base)]">
              Challenged
            </span>
            <span className="text-[11px] text-[var(--aegis-text-secondary)]">
              New evidence conflicts — {expanded ? 'hide' : 'why'}
            </span>
          </button>
          {expanded && card.challengeRationale ? (
            <p className="whitespace-pre-wrap rounded-[var(--aegis-radius-sm)] bg-[var(--aegis-surface-base)] px-2 py-1.5 text-[11px] leading-5 text-[var(--aegis-text-secondary)]">
              {card.challengeRationale}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-1.5">
        {card.confidence !== null ? (
          <span className="font-mono text-[10px] text-[var(--aegis-text-muted)]">
            {Math.round(card.confidence * 100)}% confidence
          </span>
        ) : null}
        {card.evidenceIds.map((id) => (
          <code
            key={id}
            className="rounded-[var(--aegis-radius-sm)] bg-[var(--aegis-surface-elevated)] px-1.5 py-0.5 font-mono text-[9px] text-[var(--aegis-text-secondary)]"
          >
            {id}
          </code>
        ))}
      </div>
    </li>
  );
}

export function HypothesisLedger({ runId }: { runId: string }) {
  const { ledger, isError } = useHypothesisLedger(runId);
  const createHypothesis = useCreateHypothesis(runId);
  const [statement, setStatement] = useState('');
  const [assets, setAssets] = useState('');
  const [confidence, setConfidence] = useState(50);

  const submit = () => {
    if (!statement.trim()) {
      return;
    }
    createHypothesis.mutate(
      {
        statement: statement.trim(),
        assetIds: parseAssetIds(assets),
        confidence: confidence / 100,
      },
      {
        onSuccess: () => {
          setStatement('');
          setAssets('');
          setConfidence(50);
        },
      },
    );
  };

  return (
    <div className="flex flex-col gap-3" data-testid="operator-hypotheses">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
        className="flex flex-col gap-2"
      >
        <div className="flex flex-col gap-1">
          <label
            htmlFor="hyp-statement"
            className="font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]"
          >
            Working hypothesis
          </label>
          <textarea
            id="hyp-statement"
            value={statement}
            rows={2}
            onChange={(e) => {
              setStatement(e.target.value);
            }}
            placeholder="e.g. The logistics VPN gateway is the initial access point."
            className="w-full resize-none rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-base)] px-2.5 py-1.5 text-xs text-[var(--aegis-text-primary)] placeholder:text-[var(--aegis-text-muted)] focus:border-[var(--aegis-accent)] focus:outline-none"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label
            htmlFor="hyp-assets"
            className="font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]"
          >
            Implicated assets (comma-separated)
          </label>
          <input
            id="hyp-assets"
            value={assets}
            onChange={(e) => {
              setAssets(e.target.value);
            }}
            placeholder="asset:vpn-gw, asset:jump-host"
            className="w-full rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-base)] px-2.5 py-1.5 text-xs text-[var(--aegis-text-primary)] placeholder:text-[var(--aegis-text-muted)] focus:border-[var(--aegis-accent)] focus:outline-none"
          />
        </div>
        <div className="flex items-center gap-3">
          <label
            htmlFor="hyp-confidence"
            className="font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]"
          >
            Confidence
          </label>
          <input
            id="hyp-confidence"
            type="range"
            min={0}
            max={100}
            value={confidence}
            onChange={(e) => {
              setConfidence(Number(e.target.value));
            }}
            className="flex-1 accent-[var(--aegis-accent)]"
          />
          <span className="w-9 text-right font-mono text-xs tabular-nums text-[var(--aegis-text-secondary)]">
            {confidence}%
          </span>
        </div>
        <Button
          type="submit"
          size="sm"
          disabled={!statement.trim() || createHypothesis.isPending}
          className="self-start"
        >
          {createHypothesis.isPending ? 'Pinning…' : 'Pin hypothesis'}
        </Button>
        {createHypothesis.isError ? (
          <Alert variant="error">{createHypothesis.error.message}</Alert>
        ) : null}
      </form>

      {isError ? (
        <Alert variant="warning">
          The ledger could not be loaded. Pinned hypotheses may be out of date.
        </Alert>
      ) : null}

      {ledger.cards.length === 0 ? (
        <EmptyState
          title="No hypotheses yet"
          description="Record what you think is happening. Pinned hypotheses anchor your investigation and let the bias guard flag contradicting evidence."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {ledger.cards.map((card) => (
            <LedgerCardView key={card.id} card={card} />
          ))}
        </ul>
      )}

      {ledger.collapsedNoChangeCount > 0 ? (
        <p className="text-[11px] text-[var(--aegis-text-muted)]" data-testid="hypothesis-nochange">
          {ledger.collapsedNoChangeCount} bias check
          {ledger.collapsedNoChangeCount === 1 ? '' : 's'} found no conflict.
        </p>
      ) : null}
    </div>
  );
}

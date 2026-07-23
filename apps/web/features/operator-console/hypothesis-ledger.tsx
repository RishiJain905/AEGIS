'use client';

import { useState } from 'react';

import { Badge, Button, EmptyState } from '@aegis/ui';

import { useOperatorHypotheses } from '@/features/command-surface';

function parseAssetIds(raw: string): string[] {
  return raw
    .split(',')
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
}

export function HypothesisLedger({ runId }: { runId: string }) {
  const { hypotheses, add, remove } = useOperatorHypotheses(runId);
  const [statement, setStatement] = useState('');
  const [assets, setAssets] = useState('');
  const [confidence, setConfidence] = useState(50);

  const submit = () => {
    if (!statement.trim()) {
      return;
    }
    add({
      statement,
      assetIds: parseAssetIds(assets),
      confidence: confidence / 100,
    });
    setStatement('');
    setAssets('');
    setConfidence(50);
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
        <Button type="submit" size="sm" disabled={!statement.trim()} className="self-start">
          Pin hypothesis
        </Button>
      </form>

      {hypotheses.length === 0 ? (
        <EmptyState
          title="No pinned hypotheses"
          description="Record what you think is happening. Pinned hypotheses anchor your investigation and let the bias guard flag contradicting evidence."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {hypotheses.map((hyp) => (
            <li
              key={hyp.id}
              className="flex flex-col gap-1.5 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-3 py-2"
            >
              <div className="flex items-start gap-2">
                <p className="flex-1 text-[0.8125rem] leading-5 text-[var(--aegis-text-primary)]">
                  {hyp.statement}
                </p>
                <button
                  type="button"
                  onClick={() => {
                    remove(hyp.id);
                  }}
                  aria-label="Remove hypothesis"
                  className="shrink-0 rounded-[var(--aegis-radius-sm)] px-1.5 text-[var(--aegis-text-muted)] hover:text-[var(--aegis-risk-high)]"
                >
                  ✕
                </button>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="font-mono text-[10px] text-[var(--aegis-text-muted)]">
                  {Math.round(hyp.confidence * 100)}% confidence
                </span>
                {hyp.assetIds.map((assetId) => (
                  <code
                    key={assetId}
                    className="rounded-[var(--aegis-radius-sm)] bg-[var(--aegis-surface-elevated)] px-1.5 py-0.5 font-mono text-[9px] text-[var(--aegis-text-secondary)]"
                  >
                    {assetId}
                  </code>
                ))}
                {hyp.local ? (
                  <Badge variant="outline" className="text-[9px]">
                    Session-local
                  </Badge>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

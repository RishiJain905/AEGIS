'use client';

import { useEffect } from 'react';

import { Button, Panel } from '@aegis/ui';

import { useApiClient } from '@/lib/api';
import { useReplayStore } from '@/stores/replay-store';

function formatDiffValue(value: unknown): string {
  if (value == null) {
    return '∅';
  }
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return '[unserializable]';
  }
}

export function ReplayComparisonPanel() {
  const api = useApiClient();
  const runId = useReplayStore((state) => state.runId);
  const cursor = useReplayStore((state) => state.cursor);
  const comparison = useReplayStore((state) => state.comparison);
  const setComparisonRange = useReplayStore((state) => state.setComparisonRange);
  const applyComparisonDiff = useReplayStore((state) => state.applyComparisonDiff);

  useEffect(() => {
    if (!runId || !comparison?.loading) {
      return;
    }
    const controller = new AbortController();
    void api
      .getReplayDiff(runId, comparison.leftSequence, comparison.rightSequence, controller.signal)
      .then((diff) => {
        applyComparisonDiff(diff);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        applyComparisonDiff(
          null,
          'REPLAY_VALIDATION_FAILED',
          error instanceof Error ? error.message : 'Unable to compare replay positions',
        );
      });
    return () => {
      controller.abort();
    };
  }, [
    api,
    applyComparisonDiff,
    comparison?.leftSequence,
    comparison?.loading,
    comparison?.rightSequence,
    runId,
  ]);

  if (!runId || !cursor) {
    return null;
  }

  return (
    <Panel
      title="State comparison"
      description="Compare assets, relationships, risk, and incidents between two cursors"
      density="compact"
      data-testid="replay-comparison-panel"
    >
      <div className="mb-3 flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="sm"
          data-testid="replay-compare-mark-left"
          onClick={() => {
            const right = comparison?.rightSequence ?? cursor.sequence;
            setComparisonRange(cursor.sequence, right);
          }}
        >
          Set left = {cursor.sequence}
        </Button>
        <Button
          variant="outline"
          size="sm"
          data-testid="replay-compare-mark-right"
          onClick={() => {
            const left = comparison?.leftSequence ?? Math.max(0, cursor.sequence - 50);
            setComparisonRange(left, cursor.sequence);
          }}
        >
          Set right = {cursor.sequence}
        </Button>
      </div>

      {!comparison ? (
        <p className="text-sm text-[var(--aegis-text-secondary)]">
          Mark two replay positions to inspect meaningful differences.
        </p>
      ) : null}

      {comparison?.loading ? <p role="status">Loading comparison…</p> : null}
      {comparison?.errorMessage ? (
        <p role="alert" data-testid="replay-comparison-error">
          {comparison.errorMessage}
        </p>
      ) : null}
      {comparison?.diff ? (
        <div data-testid="replay-comparison-result">
          <p className="mb-2 text-xs text-[var(--aegis-text-secondary)]">
            {comparison.leftLabel} → {comparison.rightLabel} ·{' '}
            {comparison.diff.equivalent
              ? 'Equivalent'
              : `${String(comparison.diff.entries.length)} changes`}
          </p>
          <ul className="flex flex-col gap-1">
            {comparison.diff.entries.map((entry) => (
              <li
                key={`${entry.path}-${entry.changeType}`}
                className="rounded border border-[var(--aegis-border-subtle)] px-2 py-1 text-xs"
                data-testid="replay-comparison-entry"
              >
                <span className="font-mono">{entry.path}</span>
                <span className="mx-2 text-[var(--aegis-text-secondary)]">{entry.changeType}</span>
                <span>
                  {formatDiffValue(entry.before)} → {formatDiffValue(entry.after)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Panel>
  );
}

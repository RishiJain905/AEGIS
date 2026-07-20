'use client';

/**
 * Shared presentation primitives for the reporting surfaces (SCRIBE panel,
 * after-action review, reports index). Presentation only — no data fetching.
 *
 * Design goals:
 *  - Long, opaque identifiers and checksums (including placeholder all-'a'
 *    strings) are ALWAYS truncated so they can never blow out a column, and
 *    always carry a copy affordance plus a native hover title with the full
 *    value.
 *  - Score magnitudes render as accessible meters (numeric value always shown,
 *    band colour drawn from the reserved status palette — never colour alone).
 */

import { forwardRef, useCallback, useState, type ReactNode } from 'react';

import type { ReportClaimCategoryV1 } from '@aegis/contracts-ts';
import { cn, typographyTokens } from '@aegis/ui';

/* ------------------------------------------------------------------ */
/* Copy affordance                                                     */
/* ------------------------------------------------------------------ */

function CopyGlyph({ copied }: { copied: boolean }) {
  if (copied) {
    return (
      <svg viewBox="0 0 16 16" width="12" height="12" fill="none" aria-hidden="true">
        <path
          d="M3.5 8.5 6.5 11.5 12.5 5"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" fill="none" aria-hidden="true">
      <rect x="5" y="5" width="8" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
      <path
        d="M11 5V4a1.5 1.5 0 0 0-1.5-1.5H4A1.5 1.5 0 0 0 2.5 4v5.5A1.5 1.5 0 0 0 4 11h1"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export interface CopyButtonProps {
  value: string;
  label: string;
  className?: string;
}

export function CopyButton({ value, label, className }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    const clipboard = typeof navigator !== 'undefined' ? navigator.clipboard : undefined;
    const done = () => {
      setCopied(true);
      window.setTimeout(() => {
        setCopied(false);
      }, 1400);
    };
    try {
      const result = clipboard?.writeText(value);
      if (result && typeof result.then === 'function') {
        result.then(done).catch(() => {
          /* clipboard unavailable — silently ignore */
        });
      } else {
        done();
      }
    } catch {
      /* clipboard unavailable (jsdom / insecure context) — ignore */
    }
  }, [value]);

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={copied ? `${label} copied` : `Copy ${label}`}
      title={copied ? 'Copied' : `Copy ${label}`}
      className={cn(
        'inline-flex size-5 flex-none items-center justify-center rounded-[var(--aegis-radius-sm)] border border-transparent text-[var(--aegis-text-muted)] transition-colors',
        'hover:border-[var(--aegis-border-subtle)] hover:bg-[var(--aegis-surface-hover)] hover:text-[var(--aegis-text-primary)]',
        'focus-visible:outline-none focus-visible:ring-[length:var(--aegis-focus-width)] focus-visible:ring-[var(--aegis-focus-ring)]',
        copied ? 'text-[var(--aegis-status-normal)]' : '',
        className,
      )}
    >
      <CopyGlyph copied={copied} />
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Mono identifier / checksum chip                                     */
/* ------------------------------------------------------------------ */

function middleTruncate(value: string, head: number, tail: number): string {
  if (value.length <= head + tail + 1) {
    return value;
  }
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

export interface MonoChipProps {
  value: string | null | undefined;
  label: string;
  /**
   * `checksum` middle-truncates long hashes to head…tail; `id` relies on CSS
   * ellipsis so short ids stay whole but long ones never overflow.
   */
  variant?: 'checksum' | 'id';
  copyable?: boolean;
  className?: string;
}

/**
 * A monospace chip that renders an identifier or checksum without ever
 * overflowing its container. The full value is always available via the native
 * hover title and (by default) a copy button.
 */
export function MonoChip({
  value,
  label,
  variant = 'id',
  copyable = true,
  className,
}: MonoChipProps) {
  if (!value) {
    return (
      <span className={cn(typographyTokens.monoSm, 'text-[var(--aegis-text-faint)]', className)}>
        —
      </span>
    );
  }

  const display = variant === 'checksum' ? middleTruncate(value, 10, 6) : value;

  return (
    <span
      className={cn(
        'inline-flex min-w-0 max-w-full items-center gap-1 rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)]/70 px-1.5 py-0.5 align-middle',
        className,
      )}
    >
      <span
        className={cn(typographyTokens.monoSm, 'truncate text-[var(--aegis-text-secondary)]')}
        title={value}
      >
        {display}
      </span>
      {copyable ? <CopyButton value={value} label={label} /> : null}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Evidence-reference chip (shared)                                    */
/* ------------------------------------------------------------------ */

export interface CitationRefProps {
  /** The citation kind tag (e.g. `event`, `evidence`, `hypothesis`). */
  kind: string;
  /** The opaque, copy-correlatable reference id (`evt_*`, `evidence:*`, …). */
  referenceId: string;
  /** Optional source sequence number, rendered as a trailing mono caption. */
  sequence?: number | null;
  className?: string;
}

/**
 * The single evidence-reference chip shared by every reporting surface (the
 * reports workspace claim grid and the SCRIBE inspector panel). Before this,
 * the same "kind tag + reference id" concept had two ad-hoc treatments that
 * drifted in size and spacing; this renders them identically — a formal
 * `eyebrow`-scale kind tag next to a copy-safe `mono-sm` identifier.
 */
export function CitationRef({ kind, referenceId, sequence, className }: CitationRefProps) {
  return (
    <span className={cn('inline-flex items-center gap-1', className)}>
      <span
        className={cn(
          typographyTokens.eyebrow,
          'flex-none rounded-[var(--aegis-radius-sm)] bg-[var(--aegis-surface-raised)] px-1 py-0.5 text-[var(--aegis-text-secondary)]',
        )}
      >
        {kind}
      </span>
      <MonoChip value={referenceId} label="citation reference" copyable={false} />
      {sequence !== null && sequence !== undefined ? (
        <span className={cn(typographyTokens.monoSm, 'flex-none text-[var(--aegis-text-muted)]')}>
          seq {String(sequence)}
        </span>
      ) : null}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Metadata row (label + value)                                        */
/* ------------------------------------------------------------------ */

export function MetaRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1">
      <span className="flex-none text-[0.7rem] font-medium uppercase tracking-[0.07em] text-[var(--aegis-text-muted)]">
        {label}
      </span>
      <span className="flex min-w-0 items-center justify-end gap-1 text-right">{children}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Section label                                                       */
/* ------------------------------------------------------------------ */

export function SectionLabel({
  children,
  count,
  className,
}: {
  children: ReactNode;
  count?: number;
  className?: string;
}) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <h3 className="font-[family-name:var(--aegis-font-display)] text-[0.7rem] font-semibold uppercase tracking-[0.12em] text-[var(--aegis-text-secondary)]">
        {children}
      </h3>
      {typeof count === 'number' ? (
        <span className="rounded-full bg-[var(--aegis-surface-raised)] px-1.5 py-0.5 font-[family-name:var(--aegis-font-mono)] text-[0.65rem] leading-none text-[var(--aegis-text-muted)] tabular-nums">
          {count}
        </span>
      ) : null}
      <span
        aria-hidden="true"
        className="h-px flex-1 bg-gradient-to-r from-[var(--aegis-border-default)] to-transparent"
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Score band + meter                                                  */
/* ------------------------------------------------------------------ */

interface ScoreBand {
  fill: string;
  text: string;
  soft: string;
}

/** Map a 0–100 percentage onto the reserved status palette. */
export function scoreBand(pct: number): ScoreBand {
  if (pct >= 80) {
    return {
      fill: 'bg-[var(--aegis-status-normal)]',
      text: 'text-[var(--aegis-status-normal)]',
      soft: 'bg-[var(--aegis-status-normal-bg)]',
    };
  }
  if (pct >= 60) {
    return {
      fill: 'bg-[var(--aegis-accent-cyan)]',
      text: 'text-[var(--aegis-accent-cyan)]',
      soft: 'bg-[var(--aegis-accent-soft)]',
    };
  }
  if (pct >= 40) {
    return {
      fill: 'bg-[var(--aegis-status-suspicious)]',
      text: 'text-[var(--aegis-status-suspicious)]',
      soft: 'bg-[var(--aegis-status-suspicious-bg)]',
    };
  }
  return {
    fill: 'bg-[var(--aegis-status-compromised)]',
    text: 'text-[var(--aegis-status-compromised)]',
    soft: 'bg-[var(--aegis-status-compromised-bg)]',
  };
}

export interface ScoreMeterProps {
  /** Raw score in the 0–1 range. */
  value: number;
  label: string;
  /** When true, hides the numeric percentage caption (caller renders its own). */
  hideValue?: boolean;
  className?: string;
}

/**
 * A horizontal magnitude meter. The fill is anchored to the baseline with a
 * rounded data-end; the numeric percentage is always shown so identity never
 * rests on colour alone.
 */
export function ScoreMeter({ value, label, hideValue = false, className }: ScoreMeterProps) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  const band = scoreBand(pct);

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div
        role="meter"
        aria-label={`${label} score`}
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuetext={`${String(pct)} percent`}
        className="relative h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-[var(--aegis-surface-elevated)] ring-1 ring-inset ring-[var(--aegis-border-subtle)]"
      >
        <div
          className={cn(
            'absolute inset-y-0 left-0 rounded-full motion-safe:transition-[width] motion-safe:duration-[var(--aegis-motion-duration-slow)] motion-safe:ease-[var(--aegis-motion-ease-decelerate)]',
            band.fill,
          )}
          style={{ width: `${String(Math.max(pct, pct > 0 ? 3 : 0))}%` }}
        />
      </div>
      {hideValue ? null : (
        <span
          className={cn(
            'w-9 flex-none text-right font-mono text-xs font-semibold tabular-nums',
            band.text,
          )}
        >
          {pct}%
        </span>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Claim type badge                                                    */
/* ------------------------------------------------------------------ */

type ClaimTone = 'fact' | 'signal' | 'agent' | 'inference' | 'unsupported' | 'human';

const CLAIM_META: Record<ReportClaimCategoryV1, { label: string; tone: ClaimTone }> = {
  observed_fact: { label: 'Observed fact', tone: 'fact' },
  persisted_event: { label: 'Persisted event', tone: 'fact' },
  investigation_evidence: { label: 'Investigation evidence', tone: 'fact' },
  detection_score: { label: 'Detection score', tone: 'signal' },
  graph_risk: { label: 'Graph risk', tone: 'signal' },
  oracle_hypothesis: { label: 'ORACLE hypothesis', tone: 'agent' },
  bastion_proposal: { label: 'BASTION proposal', tone: 'agent' },
  warden_policy_decision: { label: 'WARDEN decision', tone: 'agent' },
  human_decision: { label: 'Human decision', tone: 'human' },
  agent_inference: { label: 'Agent inference', tone: 'inference' },
  uncertain: { label: 'Uncertain', tone: 'inference' },
  unsupported: { label: 'Unsupported', tone: 'unsupported' },
};

const CLAIM_TONE_CLASS: Record<ClaimTone, string> = {
  fact: 'text-[var(--aegis-status-normal)] border-[var(--aegis-status-normal)]/35 bg-[var(--aegis-status-normal-bg)]',
  signal:
    'text-[var(--aegis-accent-cyan)] border-[var(--aegis-accent-line)]/50 bg-[var(--aegis-accent-soft)]',
  agent:
    'text-[var(--aegis-status-contained)] border-[var(--aegis-status-contained)]/35 bg-[var(--aegis-status-contained-bg)]',
  inference:
    'text-[var(--aegis-status-suspicious)] border-[var(--aegis-status-suspicious)]/35 bg-[var(--aegis-status-suspicious-bg)]',
  unsupported:
    'text-[var(--aegis-status-compromised)] border-[var(--aegis-status-compromised)]/40 bg-[var(--aegis-status-compromised-bg)]',
  human:
    'text-[var(--aegis-text-secondary)] border-[var(--aegis-border-default)] bg-[var(--aegis-surface-raised)]',
};

export function claimCategoryLabel(category: ReportClaimCategoryV1): string {
  return CLAIM_META[category].label;
}

export const ClaimTypeBadge = forwardRef<
  HTMLSpanElement,
  { category: ReportClaimCategoryV1; className?: string }
>(({ category, className }, ref) => {
  const meta = CLAIM_META[category];
  return (
    <span
      ref={ref}
      data-claim-kind={meta.tone}
      className={cn(
        'inline-flex min-h-5 items-center rounded-full border px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-[0.04em]',
        CLAIM_TONE_CLASS[meta.tone],
        className,
      )}
    >
      {meta.label}
    </span>
  );
});
ClaimTypeBadge.displayName = 'ClaimTypeBadge';

/* ------------------------------------------------------------------ */
/* Pill (small neutral tag)                                            */
/* ------------------------------------------------------------------ */

export function Pill({
  children,
  tone = 'neutral',
  className,
}: {
  children: ReactNode;
  tone?: 'neutral' | 'accent' | 'warning';
  className?: string;
}) {
  const toneClass =
    tone === 'accent'
      ? 'text-[var(--aegis-accent-cyan)] border-[var(--aegis-accent-line)]/50 bg-[var(--aegis-accent-soft)]'
      : tone === 'warning'
        ? 'text-[var(--aegis-status-suspicious)] border-[var(--aegis-status-suspicious)]/35 bg-[var(--aegis-status-suspicious-bg)]'
        : 'text-[var(--aegis-text-secondary)] border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)]';
  return (
    <span
      className={cn(
        'inline-flex min-h-5 items-center gap-1 rounded-full border px-2 py-0.5 text-[0.65rem] font-medium tracking-[0.02em]',
        toneClass,
        className,
      )}
    >
      {children}
    </span>
  );
}

'use client';

import { cn } from '@aegis/ui';
import type { HTMLAttributes, ReactNode } from 'react';

/**
 * Shared presentational primitives for the inspector / context-channel surfaces.
 * They exist to give every inspector section one spacing rhythm and a clear
 * label/value hierarchy (muted, small, uppercase labels; prominent mono values)
 * inside the narrow context column, and to keep long IDs/checksums from blowing
 * out the panel width.
 */

/** A labelled block: eyebrow label above its content, comfortable vertical rhythm. */
export function InspectorField({
  label,
  children,
  className,
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex min-w-0 flex-col gap-1', className)}>
      <InspectorLabel>{label}</InspectorLabel>
      {children}
    </div>
  );
}

/** Muted, uppercase eyebrow label used consistently across inspector sections. */
export function InspectorLabel({ children, className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        'text-[0.625rem] font-semibold uppercase leading-4 tracking-[0.08em] text-[var(--aegis-text-muted)]',
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}

/**
 * A responsive 2-column metric grid. Each {@link InspectorMetric} renders an
 * aligned cell so numeric rows (Risk / Direct / Propagated / Criticality) never
 * collide. Uses a `dl` for semantics.
 */
export function InspectorMetricGrid({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <dl className={cn('grid grid-cols-2 gap-2', className)}>{children}</dl>;
}

/** A single metric cell: muted label over a prominent mono value on its own surface. */
export function InspectorMetric({
  label,
  value,
  span,
  className,
  'data-testid': testId,
}: {
  label: string;
  value: ReactNode;
  span?: boolean;
  className?: string;
  'data-testid'?: string;
}) {
  return (
    <div
      className={cn(
        'flex min-w-0 flex-col gap-1 rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)] px-3 py-2',
        span && 'col-span-2',
        className,
      )}
    >
      <dt>
        <InspectorLabel>{label}</InspectorLabel>
      </dt>
      <dd
        className="truncate font-mono text-base font-semibold leading-6 tabular-nums text-[var(--aegis-text-primary)]"
        data-testid={testId}
      >
        {value}
      </dd>
    </div>
  );
}

/**
 * A monospace identifier / checksum that truncates with an accessible tooltip so
 * long, unbroken strings (asset IDs, digests, all-`a` checksums) never widen the
 * column. The full value is available via the native `title` tooltip.
 */
export function InspectorMonoValue({
  value,
  className,
  ...props
}: { value: string } & HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn(
        'truncate font-mono text-[0.6875rem] leading-5 text-[var(--aegis-text-muted)]',
        className,
      )}
      title={value}
      {...props}
    >
      {value}
    </p>
  );
}

/** A monospace value that wraps across lines (for path chains and multi-token strings). */
export function InspectorMonoBlock({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn(
        'break-words font-mono text-[0.6875rem] leading-5 text-[var(--aegis-text-secondary)]',
        className,
      )}
      {...props}
    >
      {children}
    </p>
  );
}

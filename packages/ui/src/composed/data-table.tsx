import { forwardRef, type HTMLAttributes, type ReactNode } from 'react';

import { cn } from '../lib/cn';
import { focusTokens, typographyTokens } from '../tokens/tokens';

export interface DataTableColumn<T> {
  key: keyof T & string;
  header: string;
  render?: (row: T) => ReactNode;
}

export interface DataTableProps<T extends Record<string, unknown>>
  extends HTMLAttributes<HTMLDivElement> {
  columns: DataTableColumn<T>[];
  data: T[];
  caption?: string;
  emptyMessage?: string;
  /**
   * Alternating row backgrounds for wide, scan-heavy tables. Defaults OFF so
   * existing call sites are visually unchanged. Zebra rows carry a stable
   * `data-zebra` attribute for selection.
   */
  zebra?: boolean;
}

export function DataTable<T extends Record<string, unknown>>({
  className,
  columns,
  data,
  caption,
  emptyMessage = 'No data available',
  zebra = false,
  ...props
}: DataTableProps<T>) {
  return (
    <div
      className={cn(
        'w-full overflow-x-auto rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)] md:overflow-x-visible',
        className,
      )}
      {...props}
    >
      <table className="w-full min-w-[32rem] border-separate border-spacing-0 text-sm">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead>
          <tr className="bg-[var(--aegis-surface-raised)] text-left text-[var(--aegis-text-secondary)]">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cn(
                  'border-b border-[var(--aegis-border-default)] px-3 py-2',
                  typographyTokens.eyebrow,
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-10 text-center text-[var(--aegis-text-muted)]"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                tabIndex={0}
                data-zebra={zebra ? 'true' : undefined}
                className={cn(
                  'text-[var(--aegis-text-primary)] transition-colors duration-[var(--aegis-motion-duration-fast)] hover:bg-[var(--aegis-surface-hover)]',
                  zebra &&
                    'odd:bg-[var(--aegis-surface-panel)] even:bg-[color-mix(in_srgb,var(--aegis-surface-panel)_96%,var(--aegis-text-primary))]',
                  focusTokens.ring,
                )}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className="border-b border-[var(--aegis-border-subtle)] px-3 py-2"
                  >
                    {column.render ? column.render(row) : String(row[column.key] ?? '')}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export type DataTableContainerProps = HTMLAttributes<HTMLDivElement>;

export const DataTableContainer = forwardRef<HTMLDivElement, DataTableContainerProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'overflow-hidden rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-default)] shadow-[var(--aegis-shadow-panel)]',
        className,
      )}
      {...props}
    />
  ),
);
DataTableContainer.displayName = 'DataTableContainer';

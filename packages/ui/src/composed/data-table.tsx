import { forwardRef, type HTMLAttributes, type ReactNode } from 'react';

import { cn } from '../lib/cn';
import { focusTokens } from '../tokens/tokens';

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
}

export function DataTable<T extends Record<string, unknown>>({
  className,
  columns,
  data,
  caption,
  emptyMessage = 'No data available',
  ...props
}: DataTableProps<T>) {
  return (
    <div className={cn('w-full overflow-x-auto md:overflow-x-visible', className)} {...props}>
      <table className="w-full min-w-[32rem] border-collapse text-sm">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead>
          <tr className="border-b border-[var(--aegis-border-default)] text-left text-[var(--aegis-text-secondary)]">
            {columns.map((column) => (
              <th key={column.key} scope="col" className="px-3 py-2 font-medium">
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
                className="px-3 py-6 text-center text-[var(--aegis-text-muted)]"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                tabIndex={0}
                className={cn(
                  'border-b border-[var(--aegis-border-subtle)] text-[var(--aegis-text-primary)] hover:bg-[var(--aegis-surface-elevated)]',
                  focusTokens.ring,
                )}
              >
                {columns.map((column) => (
                  <td key={column.key} className="px-3 py-2">
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
        'rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-default)]',
        className,
      )}
      {...props}
    />
  ),
);
DataTableContainer.displayName = 'DataTableContainer';

/**
 * @vitest-environment jsdom
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { DataTable, type DataTableColumn } from '../../src';

interface Row extends Record<string, unknown> {
  id: string;
  name: string;
}

const columns: DataTableColumn<Row>[] = [
  { key: 'id', header: 'ID' },
  { key: 'name', header: 'Name' },
];

const data: Row[] = [
  { id: '1', name: 'Alpha' },
  { id: '2', name: 'Bravo' },
  { id: '3', name: 'Charlie' },
];

describe('DataTable zebra striping', () => {
  it('defaults zebra off with no data-zebra attribute or stripe classes', () => {
    render(<DataTable columns={columns} data={data} />);

    const row = screen.getByText('Alpha').closest('tr');
    expect(row).not.toBeNull();
    expect(row).not.toHaveAttribute('data-zebra');
    expect(row?.className).not.toContain('odd:bg-');
    expect(row?.className).not.toContain('even:bg-');
  });

  it('marks zebra rows with a stable data-zebra attribute when enabled', () => {
    render(<DataTable columns={columns} data={data} zebra />);

    for (const label of ['Alpha', 'Bravo', 'Charlie']) {
      const row = screen.getByText(label).closest('tr');
      expect(row).toHaveAttribute('data-zebra', 'true');
    }
  });

  it('keeps odd rows on the base surface-panel token', () => {
    render(<DataTable columns={columns} data={data} zebra />);

    const oddRow = screen.getByText('Alpha').closest('tr');
    expect(oddRow?.className).toContain('odd:bg-[var(--aegis-surface-panel)]');
  });

  it('tints even rows via a theme-proof color-mix stripe rather than a flat token', () => {
    render(<DataTable columns={columns} data={data} zebra />);

    const evenRow = screen.getByText('Bravo').closest('tr');
    // A flat `surface-elevated` token collapses to the same value as
    // `surface-panel` in the light theme, making the stripe invisible.
    // The stripe must instead be a relative tint so it stays visible in
    // both themes.
    expect(evenRow?.className).toContain(
      'even:bg-[color-mix(in_srgb,var(--aegis-surface-panel)_96%,var(--aegis-text-primary))]',
    );
    expect(evenRow?.className).not.toContain('even:bg-[var(--aegis-surface-elevated)]');
  });

  it('keeps row hover above the zebra stripe', () => {
    render(<DataTable columns={columns} data={data} zebra />);

    const row = screen.getByText('Alpha').closest('tr');
    expect(row?.className).toContain('hover:bg-[var(--aegis-surface-hover)]');
  });
});

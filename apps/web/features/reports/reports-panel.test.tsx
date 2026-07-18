import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { useAfterActionReport, useReportVersions } = vi.hoisted(() => ({
  useAfterActionReport: vi.fn(),
  useReportVersions: vi.fn(),
}));

vi.mock('@/features/reports/use-report-queries', () => ({
  useAfterActionReport,
  useReportVersions,
}));

import { ReportsPanel } from '@/features/reports/reports-panel';

describe('ReportsPanel readiness states', () => {
  beforeEach(() => {
    useAfterActionReport.mockReset();
    useReportVersions.mockReset();
    useReportVersions.mockReturnValue({ isPending: false, isError: false, data: [] });
  });

  afterEach(() => {
    cleanup();
  });

  it('shows a not-ready empty state (not an infinite spinner) when the report 404s on a RUNNING run', () => {
    // A RUNNING run has no report yet: the query settles to error with no data.
    useAfterActionReport.mockReturnValue({
      isPending: false,
      isError: true,
      data: undefined,
    });

    render(<ReportsPanel runId="run_running" />);

    expect(screen.getByText('After-action report not ready')).toBeInTheDocument();
    expect(screen.queryByText('Loading after-action report')).not.toBeInTheDocument();
  });

  it('shows the spinner only while genuinely fetching', () => {
    useAfterActionReport.mockReturnValue({
      isPending: true,
      isError: false,
      data: undefined,
    });

    render(<ReportsPanel runId="run_pending" />);

    expect(screen.getByText('Loading after-action report')).toBeInTheDocument();
  });

  it('renders the report content once it is available', () => {
    useAfterActionReport.mockReturnValue({
      isPending: false,
      isError: false,
      data: {
        versionNumber: 1,
        groundingFallback: false,
        narrativeProviderId: null,
        executiveSummary: 'Summary',
        checksum: 'abc123',
        sessionId: null,
        taskId: null,
        timeline: [],
        claims: [],
      },
    });

    render(<ReportsPanel runId="run_done" />);

    expect(screen.getByTestId('reports-panel')).toBeInTheDocument();
    expect(screen.queryByText('Loading after-action report')).not.toBeInTheDocument();
  });
});

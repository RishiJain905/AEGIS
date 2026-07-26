import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { useAfterActionReport, useReportVersions, useRunStatusForReports } = vi.hoisted(() => ({
  useAfterActionReport: vi.fn(),
  useReportVersions: vi.fn(),
  useRunStatusForReports: vi.fn(),
}));

vi.mock('@/features/reports/use-report-queries', async () => {
  const actual = await vi.importActual<typeof import('@/features/reports/use-report-queries')>(
    '@/features/reports/use-report-queries',
  );
  return {
    ...actual,
    useAfterActionReport,
    useReportVersions,
    useRunStatusForReports,
  };
});

import { ReportsPanel } from '@/features/reports/reports-panel';

describe('ReportsPanel readiness states', () => {
  beforeEach(() => {
    useAfterActionReport.mockReset();
    useReportVersions.mockReset();
    useRunStatusForReports.mockReset();
    useReportVersions.mockReturnValue({ isPending: false, isError: false, data: [] });
  });

  afterEach(() => {
    cleanup();
  });

  it('never fires the report/version queries while the run is still active — no guaranteed 404 on every load', () => {
    useRunStatusForReports.mockReturnValue({ isPending: false, data: { status: 'running' } });
    useAfterActionReport.mockReturnValue({ isPending: false, isError: false, data: undefined });

    render(<ReportsPanel runId="run_running" />);

    expect(screen.getByText('After-action report not ready')).toBeInTheDocument();
    expect(useAfterActionReport).toHaveBeenCalledWith('run_running', { enabled: false });
    expect(useReportVersions).toHaveBeenCalledWith('run_running', { enabled: false });
  });

  it('shows the spinner while the run status itself is still loading, not the not-ready state', () => {
    useRunStatusForReports.mockReturnValue({ isPending: true, data: undefined });
    useAfterActionReport.mockReturnValue({ isPending: true, isError: false, data: undefined });

    render(<ReportsPanel runId="run_unknown" />);

    expect(screen.getByText('Loading after-action report')).toBeInTheDocument();
    expect(screen.queryByText('After-action report not ready')).not.toBeInTheDocument();
  });

  it('enables the report query once the run has reached a terminal status', () => {
    useRunStatusForReports.mockReturnValue({ isPending: false, data: { status: 'stopped' } });
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
    expect(useAfterActionReport).toHaveBeenCalledWith('run_done', { enabled: true });
  });

  it('still shows the not-ready state on a real report-query failure for an eligible run (not gating, an actual error)', () => {
    useRunStatusForReports.mockReturnValue({ isPending: false, data: { status: 'completed' } });
    useAfterActionReport.mockReturnValue({ isPending: false, isError: true, data: undefined });

    render(<ReportsPanel runId="run_done_but_failed" />);

    expect(screen.getByText('After-action report not ready')).toBeInTheDocument();
  });
});

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const { useThreatTempo } = vi.hoisted(() => ({ useThreatTempo: vi.fn() }));
vi.mock('@/features/live-run/hooks/use-threat-tempo', () => ({ useThreatTempo }));

import { ThreatTempoIndicator, threatTempoBand } from './threat-tempo-indicator';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

function mockReading(reading: unknown) {
  useThreatTempo.mockReturnValue({ data: reading });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('threatTempoBand', () => {
  it('escalates label and pulse with pressure', () => {
    expect(threatTempoBand(0.0).label).toBe('quiet');
    expect(threatTempoBand(0.2).label).toBe('low');
    expect(threatTempoBand(0.5).label).toBe('elevated');
    expect(threatTempoBand(0.7).label).toBe('high');
    expect(threatTempoBand(0.9).label).toBe('critical');
    // Only high/critical pulse (and only ever under motion-safe).
    expect(threatTempoBand(0.5).pulse).toBe(false);
    expect(threatTempoBand(0.7).pulse).toBe(true);
    expect(threatTempoBand(0.9).pulse).toBe(true);
  });
});

describe('ThreatTempoIndicator', () => {
  it('renders nothing before the first reading', () => {
    mockReading(undefined);
    const { container } = render(<ThreatTempoIndicator runId={RUN_ID} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when the run carries no fog tension', () => {
    mockReading({ tempo: null, loadoutEnabled: true });
    const { container } = render(<ThreatTempoIndicator runId={RUN_ID} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when the loadout opts out', () => {
    mockReading({ tempo: 0.9, loadoutEnabled: false });
    const { container } = render(<ThreatTempoIndicator runId={RUN_ID} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('surfaces a qualitative meter with accessible value when tempo is present', () => {
    mockReading({ tempo: 0.9, loadoutEnabled: true });
    render(<ThreatTempoIndicator runId={RUN_ID} />);
    const meter = screen.getByRole('meter');
    expect(meter).toHaveAttribute('aria-label', 'Threat tempo: critical');
    expect(meter).toHaveAttribute('aria-valuenow', '90');
  });

  it('reads quiet at low pressure', () => {
    mockReading({ tempo: 0.05, loadoutEnabled: true });
    render(<ThreatTempoIndicator runId={RUN_ID} />);
    expect(screen.getByRole('meter')).toHaveAttribute('aria-label', 'Threat tempo: quiet');
  });
});

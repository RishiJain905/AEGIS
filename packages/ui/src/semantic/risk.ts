import { riskTokens, type RiskToken } from '../tokens/tokens';

export type RiskBand = 'low' | 'medium' | 'high' | 'critical';

export interface RiskPresentation {
  band: RiskBand;
  label: string;
  tokenClass: string;
  ariaLabel: string;
}

const riskBandPresentation: Record<RiskBand, RiskPresentation> = {
  low: {
    band: 'low',
    label: 'Low risk',
    tokenClass: riskTokens.low,
    ariaLabel: 'Risk band: Low',
  },
  medium: {
    band: 'medium',
    label: 'Medium risk',
    tokenClass: riskTokens.medium,
    ariaLabel: 'Risk band: Medium',
  },
  high: {
    band: 'high',
    label: 'High risk',
    tokenClass: riskTokens.high,
    ariaLabel: 'Risk band: High',
  },
  critical: {
    band: 'critical',
    label: 'Critical risk',
    tokenClass: riskTokens.critical,
    ariaLabel: 'Risk band: Critical',
  },
};

export function getRiskBandPresentation(band: RiskBand): RiskPresentation {
  return riskBandPresentation[band];
}

export function scoreToRiskBand(score: number): RiskBand {
  if (score >= 0.85) return 'critical';
  if (score >= 0.65) return 'high';
  if (score >= 0.35) return 'medium';
  return 'low';
}

export function getRiskTokenForBand(band: RiskBand): RiskToken {
  return band;
}

export function normalizeRiskBand(value: string): RiskBand {
  const normalized = value.toLowerCase();
  if (
    normalized === 'low' ||
    normalized === 'medium' ||
    normalized === 'high' ||
    normalized === 'critical'
  ) {
    return normalized;
  }
  return 'medium';
}

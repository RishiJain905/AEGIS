import type { GraphEdgeV1, GraphNodeV1 } from '@aegis/contracts-ts';
import { scoreToRiskBand, type RiskBand } from '@aegis/ui';

export interface NodeVisualStyle {
  color: string;
  size: number;
  borderColor: string;
  riskBand: RiskBand;
  statusColor: string;
}

export interface EdgeVisualStyle {
  color: string;
  size: number;
  type: 'line' | 'arrow';
  opacity: number;
}

const ASSET_TYPE_COLORS: Record<string, string> = {
  service: '#36a9e1',
  device: '#8999ff',
  user: '#49cfc5',
  identity: '#5ad3bd',
  database: '#efb85a',
  control: '#ed6b79',
  ai_model: '#cf88e8',
};

const STATUS_COLORS: Record<string, string> = {
  normal: '#22c55e',
  suspicious: '#eab308',
  under_investigation: '#f97316',
  contained: '#6366f1',
  compromised: '#ef4444',
};

const RISK_HALO_COLORS: Record<RiskBand, string> = {
  low: '#22c55e33',
  medium: '#eab30844',
  high: '#f9731666',
  critical: '#ef444488',
};

export function getNodeVisualStyle(node: GraphNodeV1, criticalityScale = 1): NodeVisualStyle {
  const riskBand = scoreToRiskBand(node.riskScore);
  const baseColor = ASSET_TYPE_COLORS[node.assetType] ?? '#64748b';
  const size = 8 + node.criticality * 12 * criticalityScale;

  return {
    color: baseColor,
    size,
    borderColor: STATUS_COLORS[node.status] ?? '#64748b',
    riskBand,
    statusColor: STATUS_COLORS[node.status] ?? '#64748b',
  };
}

export function getRiskHaloColor(riskBand: RiskBand): string {
  return RISK_HALO_COLORS[riskBand];
}

export function getEdgeVisualStyle(edge: GraphEdgeV1): EdgeVisualStyle {
  const isInferred = edge.confidence < 0.75;
  const hasActivity = edge.eventCount > 0;
  const riskWeight = Math.min(1, edge.riskContribution);

  const confidenceOpacity = isInferred ? 0.35 : 0.4 + edge.confidence * 0.6;
  const activityOpacity = 0.3 + riskWeight * 0.5;
  return {
    color: hasActivity ? '#ef4444' : '#94a3b8',
    size: hasActivity ? 1.5 + Math.log10(edge.eventCount + 1) : 0.8,
    type: edge.directed && edge.confidence >= 0.75 ? 'arrow' : 'line',
    opacity: Math.min(1, hasActivity ? confidenceOpacity * activityOpacity : confidenceOpacity),
  };
}

export function getHighlightColor(
  mode: 'neighborhood' | 'path' | 'incident' | 'dependencies',
): string {
  switch (mode) {
    case 'neighborhood':
      return '#3b82f6';
    case 'path':
      return '#f59e0b';
    case 'incident':
      return '#ef4444';
    case 'dependencies':
      return '#8b5cf6';
    default: {
      const _exhaustive: never = mode;
      throw new Error(`Unhandled highlight mode: ${String(_exhaustive)}`);
    }
  }
}

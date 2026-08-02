import type { GraphEdgeV1, GraphNodeV1 } from '@aegis/contracts-ts';
import { scoreToRiskBand, type RiskBand } from '@aegis/ui';

import {
  RenderQualityTier,
  type RenderQualityTierValue,
} from '@/features/cinematic-graph/contracts/render-quality-tier';

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

// Node status colors mirror the dark-theme `--aegis-status-*` tokens
// (packages/ui/src/styles/tokens.css) so canvas/WebGL renderers — which cannot
// read CSS custom properties per frame — stay in lockstep with the badge/chip
// status language of the rest of the UI.
const STATUS_COLORS: Record<string, string> = {
  normal: '#63d6a2',
  suspicious: '#f58a2e',
  under_investigation: '#68d0ee',
  contained: '#9aa8ff',
  compromised: '#ff7078',
};

// Risk-band accents mirror the dark-theme `--aegis-risk-*` tokens.
const RISK_BAND_ACCENTS: Record<RiskBand, string> = {
  low: '#63d6a2',
  medium: '#f58a2e',
  high: '#ff6b35',
  critical: '#ff7078',
};

const RISK_HALO_COLORS: Record<RiskBand, string> = {
  low: '#63d6a233',
  medium: '#f58a2e44',
  high: '#ff6b3566',
  critical: '#ff707888',
};

/** Shape-per-asset-type language shared by the 2D canvas renderers, the 2D
 * legend, and the 3D billboard glyphs — defined once so the two renderers
 * cannot drift apart. */
export type NodeGlyphShape = 'circle' | 'diamond' | 'square' | 'triangle' | 'hexagon';

const NODE_SHAPES: Record<string, NodeGlyphShape> = {
  service: 'circle',
  device: 'diamond',
  database: 'square',
  identity: 'hexagon',
  user: 'hexagon',
  control: 'triangle',
  ai_model: 'hexagon',
};

export function getNodeShape(assetType: string | null): NodeGlyphShape {
  return (assetType && NODE_SHAPES[assetType]) || 'circle';
}

/** 3D size tier per asset type (§7.2): Service/Database read slightly larger,
 * mirroring the 2D legend's implicit hierarchy where circles read as more
 * central than diamonds. Presentation-only scale multiplier. */
export function getNodeSizeTier(assetType: string | null): number {
  switch (assetType) {
    case 'service':
    case 'database':
      return 1.12;
    case 'device':
      return 0.88;
    case 'user':
    case 'identity':
      return 0.94;
    default:
      return 1;
  }
}

export function getNodeVisualStyle(node: GraphNodeV1, criticalityScale = 1): NodeVisualStyle {
  const riskBand = scoreToRiskBand(node.riskScore);
  const baseColor = ASSET_TYPE_COLORS[node.assetType] ?? '#64748b';
  const size = 7 + node.criticality * 10 * criticalityScale;

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

/** Quiet neutral emissive for no-signal nodes: a warm desaturated graphite so
 * risk/status-colored nodes pop by contrast (§7.1). */
export const NEUTRAL_NODE_ACCENT = '#56524a';

export interface NodeSemanticAccent {
  /** Emissive tint driven by status (wins) or risk band, else neutral. */
  emissiveColor: string;
  /** CPU-side emissive intensity multiplier (baked into the tint by 3D). */
  emissiveIntensity: number;
  source: 'status' | 'risk' | 'none';
}

/**
 * §7.1: one accent per node from the same risk/status token values the 2D
 * legend uses. Status wins over risk (matching the 2D legend's precedence);
 * low-risk normal nodes keep a quiet neutral accent.
 */
export function getNodeSemanticAccent(
  node: Pick<GraphNodeV1, 'status' | 'riskScore'>,
): NodeSemanticAccent {
  if (node.status !== 'normal' && STATUS_COLORS[node.status] !== undefined) {
    return {
      emissiveColor: STATUS_COLORS[node.status] ?? NEUTRAL_NODE_ACCENT,
      emissiveIntensity: 0.78,
      source: 'status',
    };
  }
  const riskBand = scoreToRiskBand(node.riskScore);
  if (riskBand === 'critical' || riskBand === 'high' || riskBand === 'medium') {
    return {
      emissiveColor: RISK_BAND_ACCENTS[riskBand],
      emissiveIntensity: riskBand === 'critical' ? 0.92 : riskBand === 'high' ? 0.74 : 0.55,
      source: 'risk',
    };
  }
  return { emissiveColor: NEUTRAL_NODE_ACCENT, emissiveIntensity: 0.5, source: 'none' };
}

export function getEdgeVisualStyle(edge: GraphEdgeV1): EdgeVisualStyle {
  const isInferred = edge.confidence < 0.75;
  const hasActivity = edge.eventCount > 0;
  const riskWeight = Math.min(1, edge.riskContribution);

  const confidenceOpacity = isInferred ? 0.35 : 0.4 + edge.confidence * 0.6;
  const activityOpacity = 0.3 + riskWeight * 0.5;
  // Red is reserved for risk: an active edge only escalates toward the risk
  // accents as its risk contribution rises — routine traffic reads as calm
  // comms blue, so the attacker's path is the only red thing on the board.
  const color =
    riskWeight >= 0.8
      ? '#ff7078'
      : riskWeight >= 0.55
        ? '#ff6b35'
        : hasActivity
          ? '#36a9e1'
          : '#5d6b7e';
  return {
    color,
    size: hasActivity ? 1.5 + Math.log10(edge.eventCount + 1) : 0.8,
    type: edge.directed && edge.confidence >= 0.75 ? 'arrow' : 'line',
    opacity: Math.min(1, hasActivity ? confidenceOpacity * activityOpacity : confidenceOpacity),
  };
}

export type EdgeHighlightKind = 'neighborhood' | 'path' | 'incident' | 'dependencies';

export function getHighlightColor(mode: EdgeHighlightKind): string {
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

export interface EdgeSemanticStyle {
  color: string;
  /** Renderer-agnostic width (Sigma size units; 3D scales via its profile). */
  width: number;
  opacity: number;
  /** Incident-scope containment edges render dashed in BOTH renderers (§7.4):
   * 2D uses a literal dash pattern, 3D an equivalent dashed line material. */
  dashed: boolean;
  highlighted: boolean;
  dimmed: boolean;
}

/**
 * §7.4: the single edge color/weight rule set shared by the Sigma adapter and
 * the 3D scene mapper — default edges thin and muted, the active/selected
 * trace thicker and brighter, incident scope dashed.
 */
export function resolveEdgeSemanticStyle(input: {
  edge: GraphEdgeV1;
  highlighted: boolean;
  dimmed: boolean;
  highlightKind: EdgeHighlightKind | null;
}): EdgeSemanticStyle {
  const { edge, highlighted, dimmed, highlightKind } = input;
  const base = getEdgeVisualStyle(edge);
  const color =
    highlighted && highlightKind !== null ? getHighlightColor(highlightKind) : base.color;
  return {
    color: dimmed ? '#94a3b8' : color,
    width: highlighted ? base.size * 2 : base.size,
    opacity: dimmed ? 0.15 : highlighted ? 1 : base.opacity,
    dashed: highlighted && highlightKind === 'incident',
    highlighted,
    dimmed,
  };
}

/**
 * §7.9 quality/motion gate, shared by both renderers so the two convergence
 * paths (reduced motion, low render tier) end at the same visual state:
 * - 'full'   — per-edge animated flow with distinct phase offsets (HIGH tier).
 * - 'coarse' — MEDIUM tier: a cheaper variant. The 2D renderer collapses to a
 *   single shared phase; the 3D renderer animates only edges touching the
 *   current selection/highlight. Both are documented spec options.
 * - 'static' — zero flow animation; semantic color/weight/dash only. Reached
 *   via `prefers-reduced-motion` OR LOW/FALLBACK_2D tier — both gates converge
 *   here independently per renderer.
 */
export type EdgeFlowProfile = 'full' | 'coarse' | 'static';

export function resolveEdgeFlowProfile(
  tier: RenderQualityTierValue,
  reducedMotion: boolean,
): EdgeFlowProfile {
  if (reducedMotion) {
    return 'static';
  }
  switch (tier) {
    case RenderQualityTier.HIGH:
      return 'full';
    case RenderQualityTier.MEDIUM:
      return 'coarse';
    case RenderQualityTier.LOW:
    case RenderQualityTier.FALLBACK_2D:
      return 'static';
    default: {
      const _exhaustive: never = tier;
      throw new Error(`Unhandled render quality tier: ${String(_exhaustive)}`);
    }
  }
}

export interface EdgeFlowStyle {
  /** Flow cycles per second along the edge (direction: source → target). */
  speed: number;
  /** 0..1 brightness amplitude of the travelling segment. */
  amplitude: number;
}

/**
 * §7.9 per-edge flow parameters. Muted and slow by default; brighter and
 * faster on the active/selected trace (reinforcing — not replacing — the §7.4
 * highlight treatment). Returns null for edges that never animate (undirected
 * or dimmed). Profile gating is applied by each renderer on top of this.
 */
export function resolveEdgeFlowStyle(input: {
  directed: boolean;
  highlighted: boolean;
  dimmed: boolean;
}): EdgeFlowStyle | null {
  if (!input.directed || input.dimmed) {
    return null;
  }
  if (input.highlighted) {
    return { speed: 0.55, amplitude: 0.85 };
  }
  return { speed: 0.18, amplitude: 0.3 };
}

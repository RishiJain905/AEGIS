import {
  defaultLodPolicy,
  type LodPolicy,
  type LodRenderHints,
  type LodTier,
  resolveLodTier,
} from '../contracts/lod-policy';

export interface LodControllerInput {
  visibleNodeIds: string[];
  visibleEdgeIds: string[];
  highlightedEdgeIds: string[];
  collapsedClusterIds: string[];
  zoomRatio?: number;
  policy?: LodPolicy;
}

function selectVisibleEdges(
  visibleEdgeIds: string[],
  highlightedEdgeIds: string[],
  maxVisibleEdges: number,
): string[] {
  if (visibleEdgeIds.length <= maxVisibleEdges) {
    return visibleEdgeIds;
  }

  const highlighted = new Set(highlightedEdgeIds);
  const prioritized = [
    ...visibleEdgeIds.filter((edgeId) => highlighted.has(edgeId)),
    ...visibleEdgeIds.filter((edgeId) => !highlighted.has(edgeId)),
  ];

  return prioritized.slice(0, maxVisibleEdges);
}

export function buildLodRenderHints(input: LodControllerInput): LodRenderHints {
  const policy = input.policy ?? defaultLodPolicy;
  const tier = resolveLodTier(
    policy,
    input.visibleNodeIds.length,
    input.visibleEdgeIds.length,
    input.zoomRatio ?? 1,
  );

  return {
    tierId: tier.id,
    maxVisibleEdges: tier.maxVisibleEdges,
    labelMode: tier.labelMode,
    clusterCollapseThreshold: tier.clusterCollapseThreshold,
    edgeOpacityFloor: tier.edgeOpacityFloor,
    labelRenderedSizeThreshold: tier.labelRenderedSizeThreshold,
    labelDensity: tier.labelDensity,
    renderEdgeLabels: tier.renderEdgeLabels,
    visibleEdgeIds: selectVisibleEdges(
      input.visibleEdgeIds,
      input.highlightedEdgeIds,
      Number.isFinite(tier.maxVisibleEdges) ? tier.maxVisibleEdges : input.visibleEdgeIds.length,
    ),
    collapsedClusterIds: input.collapsedClusterIds,
  };
}

export function getLodTier(policy: LodPolicy, input: LodControllerInput): LodTier {
  return resolveLodTier(
    policy,
    input.visibleNodeIds.length,
    input.visibleEdgeIds.length,
    input.zoomRatio ?? 1,
  );
}

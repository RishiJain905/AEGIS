import { NodeStatus } from '@aegis/contracts-ts';

import { type NodeStatusValue, uiStatusTokens } from '../tokens/status-tokens';

export type StatusShape = 'circle' | 'diamond' | 'square' | 'triangle' | 'hexagon';

export type StatusIconName =
  | 'check'
  | 'alert-triangle'
  | 'search'
  | 'shield'
  | 'x-octagon'
  | 'loader'
  | 'wifi-off'
  | 'inbox';

export interface StatusPresentation {
  label: string;
  icon: StatusIconName;
  shape: StatusShape;
  tokenClass: string;
  ariaLabel: string;
}

const nodeStatusPresentation: Record<NodeStatusValue, StatusPresentation> = {
  [NodeStatus.NORMAL]: {
    label: 'Normal',
    icon: 'check',
    shape: 'circle',
    tokenClass: uiStatusTokens.normal,
    ariaLabel: 'Status: Normal — no active concerns',
  },
  [NodeStatus.SUSPICIOUS]: {
    label: 'Suspicious',
    icon: 'alert-triangle',
    shape: 'triangle',
    tokenClass: uiStatusTokens.suspicious,
    ariaLabel: 'Status: Suspicious — elevated watch',
  },
  [NodeStatus.UNDER_INVESTIGATION]: {
    label: 'Under investigation',
    icon: 'search',
    shape: 'diamond',
    tokenClass: uiStatusTokens.under_investigation,
    ariaLabel: 'Status: Under investigation — active analysis',
  },
  [NodeStatus.CONTAINED]: {
    label: 'Contained',
    icon: 'shield',
    shape: 'hexagon',
    tokenClass: uiStatusTokens.contained,
    ariaLabel: 'Status: Contained — threat isolated',
  },
  [NodeStatus.COMPROMISED]: {
    label: 'Compromised',
    icon: 'x-octagon',
    shape: 'square',
    tokenClass: uiStatusTokens.compromised,
    ariaLabel: 'Status: Compromised — confirmed breach',
  },
};

export function getNodeStatusPresentation(status: NodeStatusValue): StatusPresentation {
  return nodeStatusPresentation[status];
}

export function getOperationalStatusPresentation(
  status: 'loading' | 'error' | 'disconnected' | 'empty',
): StatusPresentation {
  const map: Record<'loading' | 'error' | 'disconnected' | 'empty', StatusPresentation> = {
    loading: {
      label: 'Loading',
      icon: 'loader',
      shape: 'circle',
      tokenClass: 'text-[var(--aegis-status-loading)] bg-[var(--aegis-status-loading-bg)]',
      ariaLabel: 'Status: Loading — data in progress',
    },
    error: {
      label: 'Error',
      icon: 'x-octagon',
      shape: 'square',
      tokenClass: 'text-[var(--aegis-status-error)] bg-[var(--aegis-status-error-bg)]',
      ariaLabel: 'Status: Error — operation failed',
    },
    disconnected: {
      label: 'Disconnected',
      icon: 'wifi-off',
      shape: 'triangle',
      tokenClass:
        'text-[var(--aegis-status-disconnected)] bg-[var(--aegis-status-disconnected-bg)]',
      ariaLabel: 'Status: Disconnected — realtime link lost',
    },
    empty: {
      label: 'Empty',
      icon: 'inbox',
      shape: 'circle',
      tokenClass: 'text-[var(--aegis-status-empty)] bg-[var(--aegis-status-empty-bg)]',
      ariaLabel: 'Status: Empty — no data available',
    },
  };
  return map[status];
}

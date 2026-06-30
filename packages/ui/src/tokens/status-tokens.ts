import { NodeStatus } from '@aegis/contracts-ts';

export const uiStatusTokens = {
  normal: 'text-[var(--aegis-status-normal)] bg-[var(--aegis-status-normal-bg)]',
  suspicious: 'text-[var(--aegis-status-suspicious)] bg-[var(--aegis-status-suspicious-bg)]',
  under_investigation:
    'text-[var(--aegis-status-under-investigation)] bg-[var(--aegis-status-under-investigation-bg)]',
  contained: 'text-[var(--aegis-status-contained)] bg-[var(--aegis-status-contained-bg)]',
  compromised: 'text-[var(--aegis-status-compromised)] bg-[var(--aegis-status-compromised-bg)]',
} as const;

export const operationalStatusTokens = {
  loading: 'text-[var(--aegis-status-loading)] bg-[var(--aegis-status-loading-bg)]',
  error: 'text-[var(--aegis-status-error)] bg-[var(--aegis-status-error-bg)]',
  disconnected: 'text-[var(--aegis-status-disconnected)] bg-[var(--aegis-status-disconnected-bg)]',
  empty: 'text-[var(--aegis-status-empty)] bg-[var(--aegis-status-empty-bg)]',
} as const;

export type NodeStatusValue = (typeof NodeStatus)[keyof typeof NodeStatus];
export type OperationalStatus = keyof typeof operationalStatusTokens;

export const ALL_NODE_STATUSES: readonly NodeStatusValue[] = [
  NodeStatus.NORMAL,
  NodeStatus.SUSPICIOUS,
  NodeStatus.UNDER_INVESTIGATION,
  NodeStatus.CONTAINED,
  NodeStatus.COMPROMISED,
] as const;

export const ALL_OPERATIONAL_STATUSES: readonly OperationalStatus[] = [
  'loading',
  'error',
  'disconnected',
  'empty',
] as const;

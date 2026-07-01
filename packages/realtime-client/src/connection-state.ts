export type RealtimeConnectionState =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'closed';

export interface SubscriptionCursor {
  runId: string;
  channel: string;
  lastAppliedSequence: number;
}

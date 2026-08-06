/**
 * How the client closes a hole in the sequence stream.
 *
 * There are two ways back to correct state and they trade off against each other by
 * distance. Replaying the missing events reads them straight from the events endpoint and
 * applies them in order — exact, and for a short hole it is one request. Refetching the
 * authoritative snapshot costs a bootstrap plus a catch-up, but its cost barely moves with
 * how far behind the client is.
 *
 * Nothing used to choose between them by distance. The post-snapshot catch-up always
 * replayed, walking the events endpoint a page at a time with only `MAX_CATCH_UP_PAGES` as a
 * stop — and that stop is silent truncation, not a decision: a client tens of thousands of
 * events behind issued forty sequential paged reads, parsed twenty thousand envelopes, and
 * still finished short of the head. Its cursor then sat below the run head, so the next live
 * event read as a gap, which asked for another snapshot, which replayed another forty pages.
 *
 * This is the missing decision. Past the cap the replay is abandoned in favour of the
 * snapshot the client already holds, whose graph is authoritative world state at serve time,
 * and the cursor jumps to the run head so live delivery resumes contiguously instead of
 * looping.
 */

/**
 * Longest run of missing sequences still worth replaying event by event.
 *
 * Four pages at the events endpoint's own `EVENT_PAGE_LIMIT` of 500. Four sequential
 * round-trips is about as much latency as an operator should spend watching a frozen board
 * before an authoritative snapshot — a fixed cost, whatever the distance — is simply the
 * faster way back. Spelled out rather than derived from that constant so this module stays
 * free of the fetch layer: it is pure planning, and its callers' tests mock the fetches.
 */
export const MAX_DELTA_REPLAY_DISTANCE = 2_000;

export type GapRecoveryStrategy =
  /** Nothing is missing. */
  | 'none'
  /** Short enough to replay from the events endpoint. */
  | 'replay'
  /** Too far behind to replay; rebuild from the authoritative snapshot. */
  | 'snapshot';

export interface GapRecoveryPlan {
  strategy: GapRecoveryStrategy;
  /** Count of missing sequences, inclusive of both ends. Zero when nothing is missing. */
  distance: number;
  /** First missing sequence. */
  fromSequence: number;
  /** Last missing sequence. */
  toSequence: number;
}

export function planGapRecovery(input: {
  fromSequence: number;
  toSequence: number;
  /** Overridable for tests; defaults to {@link MAX_DELTA_REPLAY_DISTANCE}. */
  maxReplayDistance?: number;
}): GapRecoveryPlan {
  const { fromSequence, toSequence } = input;
  if (toSequence < fromSequence) {
    return { strategy: 'none', distance: 0, fromSequence, toSequence };
  }
  const distance = toSequence - fromSequence + 1;
  const cap = input.maxReplayDistance ?? MAX_DELTA_REPLAY_DISTANCE;
  return {
    strategy: distance > cap ? 'snapshot' : 'replay',
    distance,
    fromSequence,
    toSequence,
  };
}

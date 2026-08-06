/**
 * Per-operator deterministic seed for the guided tutorial.
 *
 * The tutorial used to pin one seed (1000) for the whole database, which derived one run id
 * for everyone: whoever launched it first owned it, and every other operator's launch was
 * refused with `RUN_OWNED_BY_ANOTHER_USER` — a hard training dead end (QA 2026-08-06, P1).
 *
 * Each operator now gets their own stable seed, derived from their user id, so their tutorial
 * run id is theirs alone: launching resumes or restarts their own run, never another
 * operator's, and the ownership gate never trips. The story is unaffected — the training
 * scenario's attack branch is fixed (single branch, weight 1.0), so every seed produces the
 * same scheduled attack events; only the baseline telemetry noise differs.
 *
 * The seed is not a secret (it is displayed in the status rail), so a plain stable hash is
 * enough — no crypto dependency, and the derivation must stay stable forever: changing it
 * would mint a new run id and orphan every operator's stored walkthrough progress.
 */

/** The legacy shared seed, kept as the fallback for a launch with no authenticated actor. */
export const LEGACY_TRAINING_SEED = 1000;

/** The server's random-seed range is [1, 2^31-1]; keep the derived seed inside it. */
const MAX_SEED = 2 ** 31 - 1;

/**
 * Derive the operator's tutorial seed from their user id.
 *
 * FNV-1a over the id, folded into [1, 2^31-1]. Stable per identity, so re-launching the
 * tutorial resolves to the same run id and the existing resume/restart machinery works
 * unchanged. A null id (no authenticated actor — unreachable inside the auth gate, but
 * guarded anyway) falls back to the legacy shared seed.
 */
export function deriveTrainingSeed(userId: string | null): number {
  if (!userId) {
    return LEGACY_TRAINING_SEED;
  }
  let hash = 0x811c9dc5;
  for (let i = 0; i < userId.length; i += 1) {
    hash ^= userId.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return 1 + ((hash >>> 0) % MAX_SEED);
}

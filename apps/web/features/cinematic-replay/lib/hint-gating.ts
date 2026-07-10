import type { PresentationHintV1, ReplayStateV1 } from '@aegis/contracts-ts';

export interface PresentationHintCandidate {
  id: string;
  revealsHiddenCause: boolean;
  hiddenCauseId?: string | null;
  requiresEvidenceIds?: string[];
}

/**
 * Safe presentation hints must never reveal hidden causes before evidence.
 * Hints with revealsHiddenCause or hiddenCauseId are rejected.
 * Hints requiring evidence IDs are dropped until those evidence records exist.
 */
export function filterSafePresentationHints(
  hints: ReadonlyArray<PresentationHintV1 | PresentationHintCandidate>,
  state: ReplayStateV1,
  warnings: string[] = [],
): PresentationHintV1[] {
  const evidenceIds = new Set(state.evidence.map((item) => item.id));
  const safe: PresentationHintV1[] = [];

  for (const hint of hints) {
    if (hint.revealsHiddenCause) {
      warnings.push(`Blocked unsafe hint ${hint.id}: revealsHiddenCause must be false.`);
      continue;
    }
    if (hint.hiddenCauseId != null) {
      warnings.push(`Blocked unsafe hint ${hint.id}: hiddenCauseId is forbidden.`);
      continue;
    }
    const required = hint.requiresEvidenceIds ?? [];
    const missingEvidence = required.filter((id) => !evidenceIds.has(id));
    if (missingEvidence.length > 0) {
      warnings.push(`Deferred hint ${hint.id}: missing evidence ${missingEvidence.join(', ')}.`);
      continue;
    }
    safe.push(hint as PresentationHintV1);
  }

  return safe;
}

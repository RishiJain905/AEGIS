import { describe, expect, it } from 'vitest';

import { getAfterActionFixture } from '@/fixtures/after-action-fixture';

describe('Phase 29 after-action acceptance', () => {
  it('AC1: golden fixture produces attributed reproducible score metadata', () => {
    const view = getAfterActionFixture();
    expect(view.score.components.length).toBeGreaterThanOrEqual(8);
    expect(view.score.provenance.gradingEngineVersion).toContain('phase29');
    expect(view.score.provenance.fingerprint).toMatch(/^sha256:/);
    expect(view.score.provenance.integrityChecksum).toMatch(/^sha256:/);
  });

  it('AC2: alternative valid responses are labelled non-authoritative', () => {
    const view = getAfterActionFixture();
    expect(view.score.validAlternatives.length).toBeGreaterThan(0);
    for (const alt of view.score.validAlternatives) {
      expect(alt.authoritative).toBe(false);
      expect(alt.description.toLowerCase()).toMatch(/counterfactual|not a fact/);
    }
  });

  it('AC3: every component is explainable from rule IDs and source refs', () => {
    const view = getAfterActionFixture();
    for (const component of view.score.components) {
      expect(component.ruleIds.length).toBeGreaterThan(0);
      expect(component.explanations.length).toBeGreaterThan(0);
      expect(component.explanations[0]?.ruleId).toBeTruthy();
    }
  });

  it('AC4: after-action review teaches what happened and why choices mattered', () => {
    const view = getAfterActionFixture();
    expect(view.score.hiddenCauseRevealed).toBe(true);
    expect(view.lessons.length).toBeGreaterThan(0);
    expect(view.timelineHighlights.length).toBeGreaterThan(0);
    expect(view.bookmarks.some((b) => b.kind === 'decision' || b.kind === 'detection')).toBe(true);
    expect(view.score.decisionReviews.length).toBeGreaterThan(0);
    expect(view.score.decisionReviews[0]?.usedFutureKnowledge).toBe(false);
  });
});

import { describe, expect, it } from 'vitest';

import { TUTORIAL_CHAPTERS, allBeats, beatById, chapterById } from './tutorial-content';
import { EMPTY_EVIDENCE } from './tutorial-contract';

const KEBAB_CASE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

describe('tutorial content', () => {
  it('has unique, kebab-case chapter ids', () => {
    const ids = TUTORIAL_CHAPTERS.map((chapter) => chapter.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) {
      expect(id).toMatch(KEBAB_CASE);
    }
  });

  it('has unique, kebab-case beat ids across the whole walkthrough', () => {
    const ids = allBeats().map((beat) => beat.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) {
      expect(id).toMatch(KEBAB_CASE);
    }
  });

  it('gives every chapter a summary and at least one beat', () => {
    for (const chapter of TUTORIAL_CHAPTERS) {
      expect(chapter.title.trim().length, chapter.id).toBeGreaterThan(0);
      expect(chapter.summary.trim().length, chapter.id).toBeGreaterThan(0);
      expect(chapter.beats.length, chapter.id).toBeGreaterThan(0);
    }
  });

  it('gives every beat a title, non-empty body and a pointer label', () => {
    for (const beat of allBeats()) {
      expect(beat.title.trim().length, beat.id).toBeGreaterThan(0);
      expect(beat.body.length, beat.id).toBeGreaterThan(0);
      for (const paragraph of beat.body) {
        expect(paragraph.trim().length, beat.id).toBeGreaterThan(0);
      }
      expect(beat.pointerLabel.trim().length, beat.id).toBeGreaterThan(0);
    }
  });

  it('puts an objective on every `do` beat and none on any `learn` beat', () => {
    for (const beat of allBeats()) {
      if (beat.kind === 'do') {
        expect(beat.objective, beat.id).toBeDefined();
      } else {
        expect(beat.objective, beat.id).toBeUndefined();
      }
    }
  });

  it('names only real evidence keys, with copy on both sides of the objective', () => {
    const evidenceKeys = new Set(Object.keys(EMPTY_EVIDENCE));
    for (const beat of allBeats()) {
      const objective = beat.objective;
      if (!objective) {
        continue;
      }
      expect(evidenceKeys.has(objective.evidence), `${beat.id}: ${objective.evidence}`).toBe(true);
      expect(objective.pending.trim().length, beat.id).toBeGreaterThan(0);
      expect(objective.done.trim().length, beat.id).toBeGreaterThan(0);
    }
  });

  it('declares a valid requirement on every objective, with a skipReason on every skippable one', () => {
    const valid = new Set(['required', 'optional', 'skippable']);
    for (const beat of allBeats()) {
      const objective = beat.objective;
      if (!objective) {
        continue;
      }
      expect(valid.has(objective.requirement), beat.id).toBe(true);
      if (objective.requirement === 'skippable') {
        expect(objective.skipReason?.trim().length ?? 0, beat.id).toBeGreaterThan(0);
      }
    }
  });

  it('uses each evidence key at most once as an objective', () => {
    const used = allBeats()
      .map((beat) => beat.objective?.evidence)
      .filter((key): key is NonNullable<typeof key> => key !== undefined);
    expect(new Set(used).size).toBe(used.length);
  });

  it('anchors are CSS attribute/id selectors, most specific first', () => {
    for (const beat of allBeats()) {
      for (const anchor of beat.anchors) {
        expect(anchor.trim(), beat.id).toBe(anchor);
        expect(anchor.startsWith('[') || anchor.startsWith('#'), `${beat.id}: ${anchor}`).toBe(
          true,
        );
      }
      // No duplicate selectors within one beat — a repeat is always a copy/paste slip.
      expect(new Set(beat.anchors).size, beat.id).toBe(beat.anchors.length);
    }
  });

  it('opens with `begin` and closes with `launch-next`', () => {
    const beats = allBeats();
    expect(beats[0]?.primaryAction).toBe('begin');
    expect(beats.at(-1)?.primaryAction).toBe('launch-next');
    const actions = beats.filter((beat) => beat.primaryAction !== undefined);
    expect(actions).toHaveLength(2);
  });

  it('groups six cockpit chapters ahead of the tour chapters', () => {
    const sections = TUTORIAL_CHAPTERS.map((chapter) => chapter.section);
    expect(sections.filter((section) => section === 'cockpit')).toHaveLength(6);
    expect(sections.indexOf('tour')).toBe(sections.lastIndexOf('cockpit') + 1);
  });

  it('resolves chapters and beats by id', () => {
    expect(chapterById('orientation')?.title).toBe('Orientation');
    expect(chapterById('nope')).toBeUndefined();
    expect(beatById('welcome')?.kind).toBe('learn');
    expect(beatById('command-isolate-host')?.kind).toBe('do');
    expect(beatById('nope')).toBeUndefined();
  });
});

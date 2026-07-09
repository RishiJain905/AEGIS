import { describe, expect, it } from 'vitest';

import { buildReplayBookmarks, dedupeTimelineMarks } from '@/features/replay/lib/bookmarks';
import { getReplayStateFixture, listReplaySnapshotsFixture } from '@/fixtures/replay-fixture';

describe('replay bookmarks and timeline dedupe', () => {
  it('builds incident and snapshot bookmarks from reconstructed state', () => {
    const runId = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
    const state = getReplayStateFixture(runId, { sequence: 500 });
    const bookmarks = buildReplayBookmarks(runId, state, listReplaySnapshotsFixture(runId));
    expect(bookmarks.some((bookmark) => bookmark.kind === 'snapshot')).toBe(true);
    expect(bookmarks.some((bookmark) => bookmark.kind === 'incident')).toBe(true);
    expect(bookmarks.map((bookmark) => bookmark.sequence)).toEqual(
      [...bookmarks.map((bookmark) => bookmark.sequence)].sort((a, b) => a - b),
    );
  });

  it('dedupes duplicate or out-of-order timeline marks by sequence', () => {
    const marks = dedupeTimelineMarks([
      { sequence: 40, eventId: 'evt_b', label: 'later' },
      { sequence: 10, eventId: 'evt_a', label: 'early' },
      { sequence: 40, eventId: 'evt_b', label: 'duplicate' },
      { sequence: 20, eventId: 'evt_c', label: 'mid' },
    ]);
    expect(marks.map((mark) => mark.sequence)).toEqual([10, 20, 40]);
    expect(marks).toHaveLength(3);
  });
});

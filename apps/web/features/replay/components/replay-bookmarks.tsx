'use client';

import { Button, Panel } from '@aegis/ui';

import { useReplayStore } from '@/stores/replay-store';

export function ReplayBookmarks() {
  const bookmarks = useReplayStore((state) => state.bookmarks);
  const selectedBookmarkId = useReplayStore((state) => state.selectedBookmarkId);
  const selectBookmark = useReplayStore((state) => state.selectBookmark);

  return (
    <Panel
      title="Incident bookmarks"
      description="Jump to detection, snapshot, and approval ranges"
      density="compact"
      data-testid="replay-bookmarks"
    >
      {bookmarks.length === 0 ? (
        <p className="text-sm text-[var(--aegis-text-secondary)]">No bookmarks for this run yet.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {bookmarks.map((bookmark) => (
            <li key={bookmark.id}>
              <Button
                variant={selectedBookmarkId === bookmark.id ? 'secondary' : 'ghost'}
                size="sm"
                className="w-full justify-start"
                data-testid={`replay-bookmark-${bookmark.id}`}
                aria-pressed={selectedBookmarkId === bookmark.id}
                onClick={() => {
                  selectBookmark(bookmark.id);
                }}
              >
                <span className="font-mono text-xs">{bookmark.sequence}</span>
                <span className="ml-2 truncate">{bookmark.label}</span>
                <span className="ml-auto text-xs uppercase text-[var(--aegis-text-secondary)]">
                  {bookmark.kind}
                </span>
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

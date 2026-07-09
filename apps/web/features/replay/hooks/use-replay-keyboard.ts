'use client';

import { useEffect } from 'react';

import { nextSpeed, previousSpeed } from '@/features/replay/lib/playback';
import { useReplayStore } from '@/stores/replay-store';

export function useReplayKeyboard() {
  const setPlaybackStatus = useReplayStore((state) => state.setPlaybackStatus);
  const setSpeed = useReplayStore((state) => state.setSpeed);
  const step = useReplayStore((state) => state.step);
  const jumpToMin = useReplayStore((state) => state.jumpToMin);
  const jumpToMax = useReplayStore((state) => state.jumpToMax);
  const selectBookmark = useReplayStore((state) => state.selectBookmark);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable)
      ) {
        return;
      }

      const state = useReplayStore.getState();
      if (!state.cursor) {
        return;
      }

      if (event.code === 'Space') {
        event.preventDefault();
        if (!state.reducedMotion) {
          setPlaybackStatus(state.playbackStatus === 'playing' ? 'paused' : 'playing');
        }
        return;
      }
      if (event.key === 'ArrowRight') {
        event.preventDefault();
        step(1);
        return;
      }
      if (event.key === 'ArrowLeft') {
        event.preventDefault();
        step(-1);
        return;
      }
      if (event.key === 'Home') {
        event.preventDefault();
        jumpToMin();
        return;
      }
      if (event.key === 'End') {
        event.preventDefault();
        jumpToMax();
        return;
      }
      if (event.key === '[') {
        event.preventDefault();
        setSpeed(previousSpeed(state.speed));
        return;
      }
      if (event.key === ']') {
        event.preventDefault();
        setSpeed(nextSpeed(state.speed));
        return;
      }
      if (event.key === 'b' || event.key === 'B') {
        event.preventDefault();
        if (state.bookmarks.length === 0) {
          return;
        }
        const currentIndex = state.bookmarks.findIndex(
          (bookmark) => bookmark.id === state.selectedBookmarkId,
        );
        const next = state.bookmarks[(currentIndex + 1) % state.bookmarks.length];
        if (next) {
          selectBookmark(next.id);
        }
      }
    }

    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [jumpToMax, jumpToMin, selectBookmark, setPlaybackStatus, setSpeed, step]);
}

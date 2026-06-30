'use client';

import { useEffect } from 'react';

import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

export function useKeyboardShortcuts() {
  const setCommandPaletteOpen = useWorkspaceUiStore((state) => state.setCommandPaletteOpen);
  const togglePanelCollapsed = useWorkspaceUiStore((state) => state.togglePanelCollapsed);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const isMeta = event.metaKey || event.ctrlKey;
      if (isMeta && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setCommandPaletteOpen(true);
        return;
      }
      if (isMeta && event.key.toLowerCase() === 'b') {
        event.preventDefault();
        togglePanelCollapsed('operationsRail');
        return;
      }
      if (isMeta && event.key.toLowerCase() === 'i') {
        event.preventDefault();
        togglePanelCollapsed('inspector');
      }
    }

    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [setCommandPaletteOpen, togglePanelCollapsed]);
}

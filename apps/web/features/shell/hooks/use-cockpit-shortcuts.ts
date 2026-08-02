'use client';

import { useEffect } from 'react';

import { useGraphVisualStore } from '@/features/operational-graph/stores/graph-visual-store';
import { isTypingTarget } from '@/lib/keyboard';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

/**
 * The cockpit's single-letter vocabulary: `I` inspector sheet · `C` copilot sheet · `T`
 * chronicle · `Escape` closes the topmost summoned surface, and with nothing summoned it
 * deselects the stage. (`A` lives with the signals stack, which owns its own resolution
 * rules.) All of it stands down inside typing contexts and modified chords, and the
 * sheets own Escape themselves while focus is inside them — this handler only hears the
 * presses they let bubble.
 */
export function useCockpitShortcuts() {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey || event.defaultPrevented) {
        return;
      }
      if (isTypingTarget(event.target)) {
        return;
      }
      const cockpit = useCockpitUiStore.getState();
      const key = event.key.toLowerCase();
      if (key === 'i') {
        event.preventDefault();
        cockpit.setInspectorSheetOpen(!cockpit.inspectorSheetOpen);
        return;
      }
      if (key === 'c') {
        event.preventDefault();
        cockpit.setCopilotSheetOpen(!cockpit.copilotSheetOpen);
        return;
      }
      if (key === 't') {
        event.preventDefault();
        cockpit.setChronicleOpen(!cockpit.chronicleOpen);
        return;
      }
      if (event.key === 'Escape') {
        if (cockpit.signalsOverlayOpen) {
          cockpit.setSignalsOverlayOpen(false);
        } else if (cockpit.chronicleOpen) {
          cockpit.setChronicleOpen(false);
        } else if (cockpit.inspectorSheetOpen) {
          cockpit.setInspectorSheetOpen(false);
        } else if (cockpit.copilotSheetOpen) {
          cockpit.setCopilotSheetOpen(false);
        } else {
          // Nothing summoned: Escape mirrors a stage click — deselect.
          useWorkspaceUiStore.getState().setSelectedEntityId(null);
          useGraphVisualStore.getState().setSelection(null, null);
        }
      }
    }

    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
    };
  }, []);
}

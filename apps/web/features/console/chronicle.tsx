'use client';

import { ContextSheet } from '@aegis/ui';

import { OpsFeedPanel } from '@/features/ops-feed';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';

export interface ChronicleProps {
  runId: string;
}

/**
 * The Chronicle — the run's temporal surface, expanded. Collapsed it is the run tape in
 * the console (position and density across the whole run); expanded it is the full ops
 * feed rising out of the tape, the same timeline magnified. Step 1 of the merge: the
 * feed rehomed into the drawer whole. Step 2 (tick alignment) trails separately and
 * nothing here advertises it.
 *
 * Opens by the tape's labelled chevron, `T`, or dragging the tape's grab handle up;
 * closes by the same three plus Escape. It sits UNDER any open context sheet — the
 * chronicle is about the whole run, sheets are about the current subject.
 */
export function Chronicle({ runId }: ChronicleProps) {
  const open = useCockpitUiStore((state) => state.chronicleOpen);
  const setOpen = useCockpitUiStore((state) => state.setChronicleOpen);

  return (
    <ContextSheet
      side="bottom"
      open={open}
      onClose={() => {
        setOpen(false);
      }}
      label="Chronicle"
      subject="The run's timeline, magnified from the tape"
      fill
      data-testid="chronicle"
      className="z-30 h-[min(26rem,70%)]"
    >
      <OpsFeedPanel runId={runId} />
    </ContextSheet>
  );
}

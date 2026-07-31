'use client';

import { ReplayRunPicker } from '@/features/replay';
import { CommandCentreShell } from '@/features/shell/components';

/**
 * Replay's run-selection state. `/replay/[runId]` is the reconstruction itself; this route
 * is how an operator gets there without already knowing a run id.
 */
export default function ReplayIndexPage() {
  return (
    <CommandCentreShell>
      <ReplayRunPicker />
    </CommandCentreShell>
  );
}

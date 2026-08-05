'use client';

import { useEffect, useState } from 'react';

/**
 * The console's result rail — where the outcome of a command appears.
 *
 * Action results used to float as a fixed card in the viewport's bottom-right corner, which
 * is precisely where the console band's copilot chip, chronicle chevron and asset verbs
 * live: the notification sat on top of the controls it was reporting on and blocked every
 * one of them.
 *
 * A result is *about the operator's hands*, so it belongs with them. This slot is a real
 * row above the console band — the same place the frozen-timeline notice speaks from — so
 * the result rises out of the console instead of covering it, and can never occlude
 * interactive chrome because it is laid out, not floated. Every action surface (command
 * bar, graph context menu, inspector menu) portals its result here, so one command reads
 * the same wherever it was ordered.
 */
export const ACTION_RESULT_SLOT_ID = 'aegis-action-result-slot';

/** Rendered once, by the console. Collapses to nothing while there is no result. */
export function ActionResultSlot() {
  return (
    <div
      id={ACTION_RESULT_SLOT_ID}
      data-testid="action-result-slot"
      className="flex justify-end empty:hidden"
    />
  );
}

/**
 * The slot element, once it is mounted. Resolved in an effect rather than during render so
 * the first paint never reaches for a DOM node that does not exist yet (and so the hook is
 * safe on the server).
 */
export function useActionResultSlot(): HTMLElement | null {
  const [slot, setSlot] = useState<HTMLElement | null>(() =>
    typeof document === 'undefined' ? null : document.getElementById(ACTION_RESULT_SLOT_ID),
  );
  useEffect(() => {
    setSlot((current) => current ?? document.getElementById(ACTION_RESULT_SLOT_ID));
  }, []);
  return slot;
}

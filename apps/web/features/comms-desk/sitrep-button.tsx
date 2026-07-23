'use client';

import { useState } from 'react';

import { Button } from '@aegis/ui';

import { CommsDeskDialog } from './comms-desk-dialog';

/** Status-strip affordance that opens the SCRIBE comms desk for a run. */
export function SitrepButton({ runId }: { runId: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={() => {
          setOpen(true);
        }}
        data-testid="sitrep-button"
      >
        SITREP
      </Button>
      <CommsDeskDialog runId={runId} open={open} onOpenChange={setOpen} />
    </>
  );
}

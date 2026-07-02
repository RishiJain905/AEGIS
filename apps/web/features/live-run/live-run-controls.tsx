'use client';

import { Button } from '@aegis/ui';

import { useLiveRun } from '@/features/live-run/live-run-provider';
import { useRunCommands } from '@/features/live-run/use-run-commands';

export function LiveRunControls() {
  const liveRun = useLiveRun();
  if (liveRun === null || !liveRun.isLiveMode) {
    return null;
  }

  const { pause, resume, stop, step } = useRunCommands(liveRun.runId);
  const locallyPaused = liveRun.state.locallyPaused;

  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="live-run-controls">
      <Button
        size="sm"
        variant="secondary"
        data-testid="live-step"
        disabled={step.isPending}
        onClick={() => {
          step.mutate();
        }}
      >
        Step
      </Button>
      <Button
        size="sm"
        variant="secondary"
        data-testid="live-pause-resume"
        disabled={pause.isPending || resume.isPending}
        onClick={() => {
          if (liveRun.state.runStatus === 'paused') {
            resume.mutate();
          } else {
            pause.mutate();
          }
        }}
      >
        {liveRun.state.runStatus === 'paused' ? 'Resume sim' : 'Pause sim'}
      </Button>
      <Button
        size="sm"
        variant="ghost"
        data-testid="live-local-pause"
        onClick={() => {
          liveRun.setLocallyPaused(!locallyPaused);
        }}
      >
        {locallyPaused ? 'Resume updates' : 'Pause updates'}
      </Button>
      <Button
        size="sm"
        variant="ghost"
        data-testid="live-resync"
        onClick={() => void liveRun.resync()}
      >
        Resync
      </Button>
      <Button
        size="sm"
        variant="ghost"
        data-testid="live-stop"
        disabled={stop.isPending}
        onClick={() => {
          stop.mutate();
        }}
      >
        Stop
      </Button>
    </div>
  );
}

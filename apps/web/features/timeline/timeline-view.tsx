'use client';

import { NodeStatus } from '@aegis/contracts-ts';
import { Button, Panel, TimelineMark } from '@aegis/ui';

import { useLiveRun } from '@/features/live-run/live-run-provider';
import { getTimelineMarks } from '@/lib/api';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

const STATUS_MAP: Record<string, (typeof NodeStatus)[keyof typeof NodeStatus]> = {
  normal: NodeStatus.NORMAL,
  suspicious: NodeStatus.SUSPICIOUS,
  under_investigation: NodeStatus.UNDER_INVESTIGATION,
  contained: NodeStatus.CONTAINED,
  compromised: NodeStatus.COMPROMISED,
  paused: NodeStatus.UNDER_INVESTIGATION,
  running: NodeStatus.NORMAL,
  stopped: NodeStatus.CONTAINED,
};

export function TimelineView() {
  const liveRun = useLiveRun();
  const collapsed = useWorkspaceUiStore(
    (state) => state.panelPreferences.regions.timeline?.collapsed ?? false,
  );
  const togglePanelCollapsed = useWorkspaceUiStore((state) => state.togglePanelCollapsed);
  const timelineCursorSequence = useWorkspaceUiStore(
    (state) => state.workspace.timelineCursorSequence,
  );
  const setTimelineCursorSequence = useWorkspaceUiStore((state) => state.setTimelineCursorSequence);

  const fixtureMarks = getTimelineMarks();
  const marks =
    liveRun !== null && liveRun.isLiveMode && liveRun.state.timelineEntries.length > 0
      ? liveRun.state.timelineEntries.map((entry) => ({
          sequence: entry.sequence,
          label: entry.label,
          timestamp: entry.timestamp,
          status: entry.status,
        }))
      : fixtureMarks;

  const description =
    liveRun !== null && liveRun.isLiveMode
      ? `Live event stream · sequence ${String(liveRun.state.lastAppliedSequence)}`
      : 'Event sequence cursor (fixture-backed)';

  if (collapsed) {
    return (
      <div
        className="flex items-center justify-between border-t border-[var(--aegis-border-default)] px-4 py-2"
        data-testid="timeline-area-collapsed"
      >
        <span className="text-xs text-[var(--aegis-text-secondary)]">Timeline collapsed</span>
        <Button
          variant="ghost"
          size="sm"
          data-testid="expand-timeline"
          onClick={() => {
            togglePanelCollapsed('timeline');
          }}
        >
          Expand
        </Button>
      </div>
    );
  }

  return (
    <Panel
      title="Timeline"
      description={description}
      density="compact"
      data-testid="timeline-area"
      className="border-t border-[var(--aegis-border-default)] rounded-none border-x-0"
    >
      <div className="flex items-center justify-end pb-2">
        <Button
          variant="ghost"
          size="sm"
          data-testid="collapse-timeline"
          onClick={() => {
            togglePanelCollapsed('timeline');
          }}
        >
          Collapse
        </Button>
      </div>
      <ol className="flex flex-col gap-2">
        {marks.map((mark) => {
          const nodeStatus = STATUS_MAP[mark.status] ?? NodeStatus.NORMAL;
          const active = timelineCursorSequence === mark.sequence;
          return (
            <TimelineMark
              key={mark.sequence}
              label={mark.label}
              timestamp={mark.timestamp}
              nodeStatus={nodeStatus}
              active={active}
              data-testid={`timeline-mark-${String(mark.sequence)}`}
              onClick={() => {
                setTimelineCursorSequence(mark.sequence);
              }}
            />
          );
        })}
      </ol>
    </Panel>
  );
}

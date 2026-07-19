'use client';

import { NodeStatus } from '@aegis/contracts-ts';
import { Button, Panel, TimelineMark } from '@aegis/ui';

import { getTimelineMarks } from '@/lib/api';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

const STATUS_MAP: Record<string, (typeof NodeStatus)[keyof typeof NodeStatus]> = {
  normal: NodeStatus.NORMAL,
  suspicious: NodeStatus.SUSPICIOUS,
  under_investigation: NodeStatus.UNDER_INVESTIGATION,
  contained: NodeStatus.CONTAINED,
  compromised: NodeStatus.COMPROMISED,
};

export function TimelineArea() {
  const collapsed = useWorkspaceUiStore(
    (state) => state.panelPreferences.regions.timeline?.collapsed ?? false,
  );
  const togglePanelCollapsed = useWorkspaceUiStore((state) => state.togglePanelCollapsed);
  const timelineCursorSequence = useWorkspaceUiStore(
    (state) => state.workspace.timelineCursorSequence,
  );
  const setTimelineCursorSequence = useWorkspaceUiStore((state) => state.setTimelineCursorSequence);

  const marks = getTimelineMarks();

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
      description="Event sequence cursor (fixture-backed)"
      density="compact"
      data-testid="timeline-area"
      className="min-h-0"
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
      <ol className="max-h-72 overflow-y-auto pr-2">
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
              onClick={() => {
                setTimelineCursorSequence(mark.sequence);
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  setTimelineCursorSequence(mark.sequence);
                }
              }}
              role="button"
              tabIndex={0}
              aria-pressed={active}
            />
          );
        })}
      </ol>
    </Panel>
  );
}

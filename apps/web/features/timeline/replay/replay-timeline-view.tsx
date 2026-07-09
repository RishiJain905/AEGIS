'use client';

import { NodeStatus } from '@aegis/contracts-ts';
import { Button, Panel, TimelineMark } from '@aegis/ui';

import { dedupeTimelineMarks } from '@/features/replay/lib/bookmarks';
import { useReplayStore } from '@/stores/replay-store';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

function statusForEventType(eventType: string): (typeof NodeStatus)[keyof typeof NodeStatus] {
  if (eventType.includes('incident') || eventType.includes('approval')) {
    return NodeStatus.UNDER_INVESTIGATION;
  }
  if (eventType.includes('action') || eventType.includes('executed')) {
    return NodeStatus.CONTAINED;
  }
  if (eventType.includes('proposal')) {
    return NodeStatus.SUSPICIOUS;
  }
  return NodeStatus.NORMAL;
}

export function ReplayTimelineView() {
  const collapsed = useWorkspaceUiStore(
    (state) => state.panelPreferences.regions.timeline?.collapsed ?? false,
  );
  const togglePanelCollapsed = useWorkspaceUiStore((state) => state.togglePanelCollapsed);
  const reconstructedState = useReplayStore((state) => state.reconstructedState);
  const cursor = useReplayStore((state) => state.cursor);
  const timelineFilter = useReplayStore((state) => state.timelineFilter);
  const setCursorSequence = useReplayStore((state) => state.setCursorSequence);
  const setPlaybackStatus = useReplayStore((state) => state.setPlaybackStatus);

  const auditEvents = reconstructedState?.auditEvents ?? [];
  const filteredEvents = auditEvents.filter((event: (typeof auditEvents)[number]) => {
    if (!timelineFilter) {
      return true;
    }
    if (
      timelineFilter.eventTypes.length > 0 &&
      !timelineFilter.eventTypes.includes(event.eventType)
    ) {
      return false;
    }
    if (timelineFilter.fromSequence != null && event.sequence < timelineFilter.fromSequence) {
      return false;
    }
    if (timelineFilter.toSequence != null && event.sequence > timelineFilter.toSequence) {
      return false;
    }
    if (
      timelineFilter.query &&
      !event.summary.toLowerCase().includes(timelineFilter.query.toLowerCase()) &&
      !event.eventType.toLowerCase().includes(timelineFilter.query.toLowerCase())
    ) {
      return false;
    }
    return true;
  });
  const marks = dedupeTimelineMarks(
    filteredEvents.map((event: (typeof filteredEvents)[number]) => ({
      eventId: event.eventId,
      sequence: event.sequence,
      label: event.summary,
      timestamp: reconstructedState?.cursor.simTime ?? 'historical',
      status: statusForEventType(event.eventType),
      eventType: event.eventType,
    })),
  );

  if (collapsed) {
    return (
      <div
        className="flex items-center justify-between border-t border-[var(--aegis-border-default)] px-4 py-2"
        data-testid="timeline-area-collapsed"
      >
        <span className="text-xs text-[var(--aegis-text-secondary)]">Historical timeline collapsed</span>
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
      title="Historical timeline"
      description={
        cursor
          ? `Shared replay cursor · sequence ${String(cursor.sequence)}`
          : 'Shared replay cursor'
      }
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
      <ol className="flex max-h-64 flex-col gap-2 overflow-auto" data-testid="replay-timeline-list">
        {marks.map((mark) => {
          const active = cursor?.sequence === mark.sequence;
          return (
            <li key={`${mark.eventId}-${String(mark.sequence)}`}>
              <TimelineMark
                label={mark.label}
                timestamp={mark.timestamp}
                nodeStatus={mark.status}
                active={active}
                data-testid={`timeline-mark-${String(mark.sequence)}`}
                onClick={() => {
                  setCursorSequence(mark.sequence);
                  setPlaybackStatus('paused');
                }}
              />
            </li>
          );
        })}
      </ol>
    </Panel>
  );
}

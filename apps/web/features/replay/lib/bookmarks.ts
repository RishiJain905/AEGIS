import type {
  ReplayBookmarkV1,
  ReplayStateV1,
  SnapshotManifestV1,
} from '@aegis/contracts-ts';

export function buildReplayBookmarks(
  runId: string,
  state: ReplayStateV1 | null,
  snapshots: SnapshotManifestV1[],
): ReplayBookmarkV1[] {
  const bookmarks: ReplayBookmarkV1[] = [];

  for (const snapshot of snapshots) {
    bookmarks.push({
      schemaVersion: 1,
      id: `bm_snapshot_${snapshot.snapshotId}`,
      runId,
      label: `Snapshot @ ${String(snapshot.sequence)}`,
      kind: 'snapshot',
      sequence: snapshot.sequence,
      toSequence: snapshot.sequence,
      incidentId: null,
      description: `Acceleration snapshot ${snapshot.snapshotId}`,
    });
  }

  for (const incident of state?.incidents ?? []) {
    const openEvent = state?.auditEvents.find((event: ReplayStateV1['auditEvents'][number]) =>
      event.eventType.includes('incident'),
    );
    const sequence = openEvent?.sequence ?? Math.max(0, (state?.cursor.sequence ?? 0) - 50);
    bookmarks.push({
      schemaVersion: 1,
      id: `bm_incident_${incident.id}`,
      runId,
      label: incident.title,
      kind: 'incident',
      sequence,
      toSequence: state?.cursor.sequence ?? sequence,
      incidentId: incident.id,
      description: `Incident focus: ${incident.state}`,
    });
  }

  for (const event of state?.auditEvents ?? []) {
    if (event.eventType.includes('approval') || event.eventType.includes('proposal')) {
      bookmarks.push({
        schemaVersion: 1,
        id: `bm_event_${event.eventId}`,
        runId,
        label: event.summary,
        kind: event.eventType.includes('approval') ? 'approval' : 'detection',
        sequence: event.sequence,
        toSequence: event.sequence,
        incidentId: null,
        description: event.eventType,
      });
    }
  }

  const seen = new Set<string>();
  return bookmarks
    .sort((left, right) => left.sequence - right.sequence)
    .filter((bookmark) => {
      if (seen.has(bookmark.id)) {
        return false;
      }
      seen.add(bookmark.id);
      return true;
    });
}

export function dedupeTimelineMarks<
  T extends { sequence: number; eventId?: string; label?: string; timestamp?: string },
>(marks: T[]): T[] {
  const bySequence = new Map<number, T>();
  for (const mark of marks) {
    const existing = bySequence.get(mark.sequence);
    if (!existing) {
      bySequence.set(mark.sequence, mark);
      continue;
    }
    if (mark.eventId && existing.eventId && mark.eventId === existing.eventId) {
      continue;
    }
    bySequence.set(mark.sequence, mark);
  }
  return [...bySequence.values()].sort((left, right) => left.sequence - right.sequence);
}

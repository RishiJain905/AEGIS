'use client';

// TEMPORARY dev-only preview route for visually verifying the 3D operations
// theater (bastion ring) with a Silent-Relay-shaped synthetic snapshot and a
// scripted attack timeline: fog of war → detection reveal → lateral spread →
// containment. Not linked from anywhere; delete before merge.

import { useEffect, useState } from 'react';

import type { GraphEdgeV1, GraphNodeV1, GraphSnapshotV1 } from '@aegis/contracts-ts';

import { CinematicGraphView } from '@/features/cinematic-graph';

const ZONES = [
  { id: 'business-unit:logistics', label: 'Logistics Operations' },
  { id: 'business-unit:communications', label: 'Communications' },
  { id: 'business-unit:identity', label: 'Identity and Access' },
  { id: 'business-unit:cloud', label: 'Cloud Platform' },
  { id: 'business-unit:endpoints', label: 'Endpoints' },
  { id: 'business-unit:data-platform', label: 'Data Platform' },
  { id: 'business-unit:security-ops', label: 'Security Operations' },
  { id: 'business-unit:ai-ops', label: 'AI Operations' },
];

const ASSET_TYPES: GraphNodeV1['assetType'][] = [
  'service',
  'service',
  'database',
  'device',
  'identity',
  'control',
  'ai_model',
];

/** Timeline phases: 0 calm+fog · 1 first detection · 2 lateral spread · 3 containment. */
function buildSnapshot(phase: number): GraphSnapshotV1 {
  const nodes: GraphNodeV1[] = [];
  const edges: GraphEdgeV1[] = [];

  ZONES.forEach((zone, zoneIndex) => {
    const count = zoneIndex < 5 ? 6 : 5;
    for (let i = 0; i < count; i += 1) {
      const id = `asset:z${String(zoneIndex)}-n${String(i)}`;
      let status: GraphNodeV1['status'] = 'normal';
      let riskScore = 0.06 + i * 0.04;
      let disclosed = true;

      // The intrusion path: identity zone patient zero → cloud lateral hop.
      if (zoneIndex === 2 && i === 0) {
        disclosed = phase >= 1;
        status = phase >= 3 ? 'contained' : phase >= 1 ? 'compromised' : 'normal';
        riskScore = phase >= 1 ? 0.92 : 0.1;
      }
      if (zoneIndex === 2 && i === 3) {
        disclosed = phase >= 2;
        status = phase >= 2 ? 'suspicious' : 'normal';
        riskScore = phase >= 2 ? 0.58 : 0.1;
      }
      if (zoneIndex === 3 && i === 0) {
        disclosed = phase >= 2;
        status = phase >= 2 ? 'compromised' : 'normal';
        riskScore = phase >= 2 ? 0.86 : 0.1;
      }
      if (zoneIndex === 4 && i === 1) {
        status = 'under_investigation';
        riskScore = 0.5;
      }
      // Ambient fog of war on a slice of every zone's outer band.
      if (status === 'normal' && i >= count - 2) {
        disclosed = false;
      }

      nodes.push({
        schemaVersion: 1,
        id,
        entityType: 'asset',
        assetType: ASSET_TYPES[i % ASSET_TYPES.length] ?? 'service',
        label: `${zone.label.split(' ')[0] ?? 'Asset'} ${['Gateway', 'Coordinator', 'Records', 'Terminal', 'Broker', 'Sentinel', 'Router'][i % 7] ?? 'Node'} ${String(i)}`,
        clusterId: zone.id,
        riskScore,
        criticality: 0.95 - i * 0.14,
        status,
        revision: phase + 1,
        disclosed,
      });
    }
  });

  const now = '2026-07-24T00:00:00.000Z';
  ZONES.forEach((_zone, zoneIndex) => {
    const count = zoneIndex < 5 ? 6 : 5;
    for (let i = 1; i < count; i += 1) {
      edges.push({
        schemaVersion: 1,
        id: `edge:z${String(zoneIndex)}-${String(i)}`,
        source: `asset:z${String(zoneIndex)}-n0`,
        target: `asset:z${String(zoneIndex)}-n${String(i)}`,
        relationshipType: 'DEPENDS_ON',
        directed: true,
        confidence: 0.9,
        riskContribution: 0.1,
        firstSeenAt: now,
        lastSeenAt: now,
        eventCount: i % 2 === 0 ? 4 : 0,
        revision: 1,
      });
    }
    if (zoneIndex > 0) {
      edges.push({
        schemaVersion: 1,
        id: `edge:cross-${String(zoneIndex)}`,
        source: `asset:z${String(zoneIndex - 1)}-n0`,
        target: `asset:z${String(zoneIndex)}-n0`,
        relationshipType: 'COMMUNICATED_WITH',
        directed: true,
        confidence: 0.85,
        riskContribution: zoneIndex === 3 && phase >= 2 ? 0.9 : 0.2,
        firstSeenAt: now,
        lastSeenAt: now,
        eventCount: 6,
        revision: 1,
      });
    }
  });

  return {
    schemaVersion: 1,
    runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    sequence: phase + 1,
    capturedAt: now,
    nodes,
    edges,
    clusters: ZONES.map((zone) => ({
      schemaVersion: 1,
      id: zone.id,
      label: zone.label,
      memberNodeIds: nodes.filter((n) => n.clusterId === zone.id).map((n) => n.id),
      revision: 1,
    })),
    revision: phase + 1,
  };
}

export default function TheaterPreviewPage() {
  const [phase, setPhase] = useState(0);
  const [snapshot, setSnapshot] = useState(() => buildSnapshot(0));

  useEffect(() => {
    if (phase >= 3) {
      return;
    }
    const timer = window.setTimeout(() => {
      setPhase(phase + 1);
      setSnapshot(buildSnapshot(phase + 1));
    }, 7000);
    return () => {
      window.clearTimeout(timer);
    };
  }, [phase]);

  return (
    <main className="min-h-screen bg-[var(--aegis-surface-base)] p-6" data-phase={phase}>
      <CinematicGraphView
        snapshot={snapshot}
        runId={snapshot.runId}
        graphRevision={snapshot.revision}
      />
    </main>
  );
}

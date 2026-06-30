import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import type { GraphDeltaV1, GraphSnapshotV1 } from '@aegis/contracts-ts';
import { graphDeltaSchema, graphSnapshotSchema, parseContract } from '@aegis/contracts-ts';

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '../../..');

export function loadContractFixture<T>(relativePath: string): T {
  const raw = readFileSync(join(repoRoot, relativePath), 'utf8');
  return JSON.parse(raw) as T;
}

export function loadGraphSnapshotFixture(relativePath: string): GraphSnapshotV1 {
  return parseContract(graphSnapshotSchema, loadContractFixture<unknown>(relativePath));
}

export function loadGraphDeltaFixture(relativePath: string): GraphDeltaV1 {
  return parseContract(graphDeltaSchema, loadContractFixture<unknown>(relativePath));
}

export function loadMediumSnapshot(): GraphSnapshotV1 {
  const raw = readFileSync(
    join(repoRoot, 'packages/graph-domain/fixtures/medium-graph-snapshot.json'),
    'utf8',
  );
  return parseContract(graphSnapshotSchema, JSON.parse(raw));
}

export function buildConnectedSnapshot(): GraphSnapshotV1 {
  return {
    schemaVersion: 1,
    runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    sequence: 10,
    capturedAt: '2026-06-30T00:00:00.000Z',
    revision: 1,
    clusters: [
      {
        schemaVersion: 1,
        id: 'business-unit:bu-platform',
        label: 'Platform',
        memberNodeIds: ['asset:svc-a', 'asset:svc-b', 'asset:device-c'],
        revision: 1,
      },
    ],
    nodes: [
      {
        schemaVersion: 1,
        id: 'asset:svc-a',
        entityType: 'asset',
        assetType: 'service',
        label: 'Service A',
        clusterId: 'business-unit:bu-platform',
        riskScore: 0.2,
        criticality: 0.8,
        status: 'normal',
        revision: 1,
      },
      {
        schemaVersion: 1,
        id: 'asset:svc-b',
        entityType: 'asset',
        assetType: 'service',
        label: 'Service B',
        clusterId: 'business-unit:bu-platform',
        riskScore: 0.5,
        criticality: 0.7,
        status: 'suspicious',
        revision: 1,
      },
      {
        schemaVersion: 1,
        id: 'asset:device-c',
        entityType: 'asset',
        assetType: 'device',
        label: 'Device C',
        clusterId: 'business-unit:bu-platform',
        riskScore: 0.1,
        criticality: 0.4,
        status: 'normal',
        revision: 1,
      },
    ],
    edges: [
      {
        schemaVersion: 1,
        id: 'edge:ab',
        source: 'asset:device-c',
        target: 'asset:svc-a',
        relationshipType: 'COMMUNICATED_WITH',
        directed: true,
        confidence: 1,
        riskContribution: 0.2,
        firstSeenAt: '2026-01-01T00:00:00.000Z',
        lastSeenAt: '2026-06-30T00:00:00.000Z',
        eventCount: 5,
        revision: 1,
      },
      {
        schemaVersion: 1,
        id: 'edge:bc',
        source: 'asset:svc-a',
        target: 'asset:svc-b',
        relationshipType: 'DEPENDS_ON',
        directed: true,
        confidence: 1,
        riskContribution: 0.3,
        firstSeenAt: '2026-01-01T00:00:00.000Z',
        lastSeenAt: '2026-06-30T00:00:00.000Z',
        eventCount: 2,
        revision: 1,
      },
    ],
  };
}

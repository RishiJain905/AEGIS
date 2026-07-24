import { describe, expect, it } from 'vitest';

import type { GraphNodeV1 } from '@aegis/contracts-ts';

import { detectRevealTransitions } from '@/features/operational-graph/semantic/reveal-detection';

function makeNode(
  id: string,
  status: GraphNodeV1['status'],
  disclosed?: boolean,
): GraphNodeV1 {
  return {
    schemaVersion: 1,
    id,
    entityType: 'asset',
    assetType: 'service',
    label: id,
    riskScore: 0.5,
    criticality: 0.5,
    status,
    revision: 1,
    disclosed,
  };
}

describe('detectRevealTransitions', () => {
  it('never fires on the first snapshot — arriving mid-run stays calm', () => {
    const { revealedNodeIds, nextState } = detectRevealTransitions(null, [
      makeNode('asset:a', 'compromised', true),
    ]);
    expect(revealedNodeIds).toEqual([]);
    expect(nextState.get('asset:a')).toEqual({ disclosed: true, status: 'compromised' });
  });

  it('fires when the fog lifts on a hostile asset', () => {
    const first = detectRevealTransitions(null, [makeNode('asset:a', 'normal', false)]);
    const second = detectRevealTransitions(first.nextState, [
      makeNode('asset:a', 'compromised', true),
    ]);
    expect(second.revealedNodeIds).toEqual(['asset:a']);
  });

  it('does not fire when a disclosed node stays normal', () => {
    const first = detectRevealTransitions(null, [makeNode('asset:a', 'normal', false)]);
    const second = detectRevealTransitions(first.nextState, [makeNode('asset:a', 'normal', true)]);
    expect(second.revealedNodeIds).toEqual([]);
  });

  it('fires on live escalation from normal to compromised or suspicious', () => {
    const first = detectRevealTransitions(null, [
      makeNode('asset:a', 'normal'),
      makeNode('asset:b', 'normal'),
      makeNode('asset:c', 'normal'),
    ]);
    const second = detectRevealTransitions(first.nextState, [
      makeNode('asset:a', 'compromised'),
      makeNode('asset:b', 'suspicious'),
      makeNode('asset:c', 'under_investigation'),
    ]);
    expect(second.revealedNodeIds).toEqual(['asset:a', 'asset:b']);
  });

  it('does not re-fire while a node stays compromised', () => {
    const first = detectRevealTransitions(null, [makeNode('asset:a', 'normal')]);
    const second = detectRevealTransitions(first.nextState, [makeNode('asset:a', 'compromised')]);
    const third = detectRevealTransitions(second.nextState, [makeNode('asset:a', 'compromised')]);
    expect(second.revealedNodeIds).toEqual(['asset:a']);
    expect(third.revealedNodeIds).toEqual([]);
  });
});

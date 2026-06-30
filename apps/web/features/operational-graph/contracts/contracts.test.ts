import { describe, expect, it } from 'vitest';

import {
  defaultGraphVisualState,
  GraphHighlightMode,
  graphVisualStateSchema,
} from '@/features/operational-graph/contracts/graph-visual-state';
import { graphSelectionSchema } from '@/features/operational-graph/contracts/graph-selection';

describe('graph visual state contracts', () => {
  it('parses default visual state', () => {
    expect(graphVisualStateSchema.parse(defaultGraphVisualState)).toEqual(defaultGraphVisualState);
  });

  it('rejects invalid highlight mode', () => {
    expect(() =>
      graphVisualStateSchema.parse({
        ...defaultGraphVisualState,
        highlightMode: 'invalid',
      }),
    ).toThrow();
  });

  it('parses graph selection with nullable fields', () => {
    const selection = graphSelectionSchema.parse({
      schemaVersion: 1,
      primaryNodeId: 'asset:svc-api-gateway',
      secondaryNodeId: null,
      selectedEdgeId: null,
    });
    expect(selection.primaryNodeId).toBe('asset:svc-api-gateway');
  });
});

describe('GraphHighlightMode exhaustiveness', () => {
  it('covers all highlight modes', () => {
    const modes = Object.values(GraphHighlightMode);
    expect(modes).toContain('none');
    expect(modes).toContain('path');
    expect(modes.length).toBe(5);
  });
});

import { z } from 'zod';

export const GRAPH_VIEW_MODE_SCHEMA_VERSION = 1;

export const GraphViewMode = {
  TWO_D: '2d',
  THREE_D: '3d',
} as const;

export type GraphViewModeValue = (typeof GraphViewMode)[keyof typeof GraphViewMode];

export const graphViewModeSchema = z.enum([GraphViewMode.TWO_D, GraphViewMode.THREE_D]);

export function assertExhaustiveGraphViewMode(value: never): never {
  throw new Error(`Unhandled graph view mode: ${String(value)}`);
}

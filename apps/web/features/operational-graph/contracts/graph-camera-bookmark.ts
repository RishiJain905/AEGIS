import { z } from 'zod';

export const GRAPH_CAMERA_BOOKMARK_SCHEMA_VERSION = 1;

export const graphCameraBookmarkSchema = z
  .object({
    schemaVersion: z.literal(GRAPH_CAMERA_BOOKMARK_SCHEMA_VERSION),
    x: z.number(),
    y: z.number(),
    ratio: z.number().positive(),
  })
  .strict();

export type GraphCameraBookmark = z.infer<typeof graphCameraBookmarkSchema>;

export const defaultGraphCameraBookmark: GraphCameraBookmark = {
  schemaVersion: GRAPH_CAMERA_BOOKMARK_SCHEMA_VERSION,
  x: 0,
  y: 0,
  ratio: 1,
};

export function parseGraphCameraBookmark(data: unknown): GraphCameraBookmark {
  return graphCameraBookmarkSchema.parse(data);
}

import { z } from 'zod';

export const CAMERA_BOOKMARK_3D_SCHEMA_VERSION = 1;

export const cameraBookmark3dSchema = z
  .object({
    schemaVersion: z.literal(CAMERA_BOOKMARK_3D_SCHEMA_VERSION),
    position: z
      .object({
        x: z.number(),
        y: z.number(),
        z: z.number(),
      })
      .strict(),
    target: z
      .object({
        x: z.number(),
        y: z.number(),
        z: z.number(),
      })
      .strict(),
    fov: z.number().positive(),
  })
  .strict();

export type CameraBookmark3D = z.infer<typeof cameraBookmark3dSchema>;

export const defaultCameraBookmark3D: CameraBookmark3D = {
  schemaVersion: CAMERA_BOOKMARK_3D_SCHEMA_VERSION,
  position: { x: 0, y: 180, z: 320 },
  target: { x: 0, y: 0, z: 0 },
  fov: 50,
};

export function parseCameraBookmark3D(data: unknown): CameraBookmark3D {
  return cameraBookmark3dSchema.parse(data);
}

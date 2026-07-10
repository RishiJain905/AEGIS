import type {
  CameraDirectiveV1,
  CinematicBeatV1,
  CinematicPlanV1,
  CinematicPlaybackSpeed,
} from '@aegis/contracts-ts';

import type { CameraBookmark3D } from '@/features/cinematic-graph/contracts/camera-bookmark-3d';
import { defaultCameraBookmark3D } from '@/features/cinematic-graph/contracts/camera-bookmark-3d';

export function speedToBeatIntervalMs(speed: CinematicPlaybackSpeed): number {
  switch (speed) {
    case '0.5x':
      return 4000;
    case '1x':
      return 2500;
    case '2x':
      return 1400;
    case '4x':
      return 800;
    default: {
      const _exhaustive: never = speed;
      return _exhaustive;
    }
  }
}

export function directiveToCameraBookmark(
  directive: CameraDirectiveV1 | undefined,
): CameraBookmark3D {
  if (!directive?.bookmark) {
    return defaultCameraBookmark3D;
  }
  return {
    schemaVersion: 1,
    position: { ...directive.bookmark.position },
    target: { ...directive.bookmark.target },
    fov: directive.bookmark.fov,
  };
}

export function findDirective(
  plan: CinematicPlanV1,
  beat: CinematicBeatV1,
): CameraDirectiveV1 | undefined {
  return plan.cameraDirectives.find((directive) => directive.id === beat.cameraDirectiveId);
}

export function beatIndexForSequence(plan: CinematicPlanV1, sequence: number): number {
  if (plan.beats.length === 0) {
    return 0;
  }
  let best = 0;
  for (let i = 0; i < plan.beats.length; i += 1) {
    const beat = plan.beats[i];
    if (beat && beat.sequence <= sequence) {
      best = i;
    } else if (beat && beat.sequence > sequence) {
      break;
    }
  }
  return best;
}

export function chapterIndexForBeat(plan: CinematicPlanV1, beat: CinematicBeatV1): number {
  const index = plan.chapters.findIndex((chapter) => chapter.id === beat.chapterId);
  return index >= 0 ? index : 0;
}

export interface CameraDirectorApplyResult {
  sequence: number;
  camera: CameraBookmark3D;
  focusEntityId: string | null;
  caption: string;
  beat: CinematicBeatV1;
  transitionMs: number;
  reducedMotionJump: boolean;
}

export function applyBeatCamera(
  plan: CinematicPlanV1,
  beatIndex: number,
): CameraDirectorApplyResult | null {
  const beat = plan.beats[beatIndex];
  if (!beat) {
    return null;
  }
  const directive = findDirective(plan, beat);
  return {
    sequence: beat.sequence,
    camera: directiveToCameraBookmark(directive),
    focusEntityId: beat.entityIds[0] ?? directive?.focusEntityIds[0] ?? null,
    caption: beat.caption,
    beat,
    transitionMs: directive?.transitionMs ?? 0,
    reducedMotionJump: directive?.reducedMotionJump ?? true,
  };
}

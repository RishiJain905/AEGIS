export const motionDurations = {
  instant: 'var(--aegis-motion-duration-instant)',
  fast: 'var(--aegis-motion-duration-fast)',
  normal: 'var(--aegis-motion-duration-normal)',
  slow: 'var(--aegis-motion-duration-slow)',
} as const;

export const motionEasings = {
  standard: 'var(--aegis-motion-ease-standard)',
  emphasis: 'var(--aegis-motion-ease-emphasis)',
  decelerate: 'var(--aegis-motion-ease-decelerate)',
} as const;

export type MotionDuration = keyof typeof motionDurations;
export type MotionEasing = keyof typeof motionEasings;

export function getMotionTransition(
  properties: string[],
  duration: MotionDuration = 'normal',
  easing: MotionEasing = 'standard',
): string {
  return properties
    .map((property) => `${property} ${motionDurations[duration]} ${motionEasings[easing]}`)
    .join(', ');
}

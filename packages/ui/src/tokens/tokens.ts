export const surfaceTokens = {
  base: 'bg-[var(--aegis-surface-base)]',
  elevated: 'bg-[var(--aegis-surface-elevated)]',
  panel: 'bg-[var(--aegis-surface-panel)]',
  rail: 'bg-[var(--aegis-surface-rail)]',
  overlay: 'bg-[var(--aegis-surface-overlay)]',
} as const;

export const typographyTokens = {
  sans: 'font-[family-name:var(--aegis-font-sans)]',
  mono: 'font-[family-name:var(--aegis-font-mono)]',
  primary: 'text-[var(--aegis-text-primary)]',
  secondary: 'text-[var(--aegis-text-secondary)]',
  muted: 'text-[var(--aegis-text-muted)]',
  uiXs: 'text-xs leading-4',
  uiSm: 'text-sm leading-5',
  uiBase: 'text-base leading-6',
  uiLg: 'text-lg leading-7',
  uiXl: 'text-xl leading-8',
  // Formal numeric scale — role-based type ramp (see design tokens §2.3).
  displayXl:
    'font-[family-name:var(--aegis-font-display)] text-[1.75rem] leading-[2.125rem] font-semibold tracking-[-0.01em]',
  displayLg:
    'font-[family-name:var(--aegis-font-display)] text-[1.25rem] leading-[1.625rem] font-semibold tracking-normal',
  displayMd:
    'font-[family-name:var(--aegis-font-display)] text-[0.8125rem] leading-[1.125rem] font-semibold uppercase tracking-[0.06em]',
  bodyLg:
    'font-[family-name:var(--aegis-font-sans)] text-[0.9375rem] leading-[1.375rem] font-normal tracking-normal',
  bodyMd:
    'font-[family-name:var(--aegis-font-sans)] text-[0.875rem] leading-[1.25rem] font-normal tracking-normal',
  bodySm:
    'font-[family-name:var(--aegis-font-sans)] text-[0.8125rem] leading-[1.125rem] font-normal tracking-normal',
  eyebrow:
    'font-[family-name:var(--aegis-font-sans)] text-[0.6875rem] leading-[1rem] font-semibold uppercase tracking-[0.08em]',
  monoMd:
    'font-[family-name:var(--aegis-font-mono)] text-[0.8125rem] leading-[1.125rem] font-medium tracking-[0.01em] tabular-nums',
  monoSm:
    'font-[family-name:var(--aegis-font-mono)] text-[0.6875rem] leading-[1rem] font-medium tracking-[0.02em] tabular-nums',
} as const;

export const spacingTokens = {
  1: 'gap-[var(--aegis-space-1)] p-[var(--aegis-space-1)]',
  2: 'gap-[var(--aegis-space-2)]',
  3: 'gap-[var(--aegis-space-3)]',
  4: 'gap-[var(--aegis-space-4)]',
  6: 'gap-[var(--aegis-space-6)]',
  8: 'gap-[var(--aegis-space-8)]',
} as const;

export const borderTokens = {
  default: 'border border-[var(--aegis-border-default)]',
  subtle: 'border border-[var(--aegis-border-subtle)]',
  strong: 'border border-[var(--aegis-border-strong)]',
  radiusSm: 'rounded-[var(--aegis-radius-sm)]',
  radiusMd: 'rounded-[var(--aegis-radius-md)]',
  radiusLg: 'rounded-[var(--aegis-radius-lg)]',
  radiusXl: 'rounded-[var(--aegis-radius-xl)]',
} as const;

export const depthTokens = {
  panel: 'shadow-[var(--aegis-shadow-panel)]',
  dialog: 'shadow-[var(--aegis-shadow-dialog)]',
  rail: 'shadow-[var(--aegis-shadow-rail)]',
} as const;

export const focusTokens = {
  ring: 'focus-visible:outline-none focus-visible:ring-[length:var(--aegis-focus-width)] focus-visible:ring-[var(--aegis-focus-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--aegis-focus-ring-offset)]',
} as const;

export const riskTokens = {
  low: 'text-[var(--aegis-risk-low)] bg-[var(--aegis-risk-low-bg)]',
  medium: 'text-[var(--aegis-risk-medium)] bg-[var(--aegis-risk-medium-bg)]',
  high: 'text-[var(--aegis-risk-high)] bg-[var(--aegis-risk-high-bg)]',
  critical: 'text-[var(--aegis-risk-critical)] bg-[var(--aegis-risk-critical-bg)]',
} as const;

export const densityTokens = {
  compact: 'gap-[var(--aegis-density-compact-gap)] p-[var(--aegis-density-compact-padding)]',
  comfortable:
    'gap-[var(--aegis-density-comfortable-gap)] p-[var(--aegis-density-comfortable-padding)]',
  spacious: 'gap-[var(--aegis-density-spacious-gap)] p-[var(--aegis-density-spacious-padding)]',
} as const;

export const breakpointTokens = {
  md: '1024px',
  lg: '1280px',
  xl: '1536px',
} as const;

export type SurfaceToken = keyof typeof surfaceTokens;
export type TypographyToken = keyof typeof typographyTokens;
export type RiskToken = keyof typeof riskTokens;
export type DensityToken = keyof typeof densityTokens;

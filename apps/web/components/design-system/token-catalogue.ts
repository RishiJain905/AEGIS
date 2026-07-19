export type TokenKind = 'color' | 'radius';

export interface DesignToken {
  /** The CSS custom property name, including the leading `--`. */
  readonly name: string;
  /** Short human label. */
  readonly label: string;
  readonly kind: TokenKind;
}

export interface TokenGroup {
  readonly id: string;
  readonly title: string;
  readonly description: string;
  readonly tokens: readonly DesignToken[];
}

function color(name: string, label: string): DesignToken {
  return { name, label, kind: 'color' };
}

function radius(name: string, label: string): DesignToken {
  return { name, label, kind: 'radius' };
}

/**
 * The AEGIS command-grid design tokens, grouped for the operational inspector.
 * Names mirror `packages/ui/src/styles/tokens.css`; values are read live from
 * the document at runtime so the inspector never drifts from the stylesheet.
 */
export const TOKEN_GROUPS: readonly TokenGroup[] = [
  {
    id: 'surfaces',
    title: 'Surfaces',
    description: 'Blue-black layers, base to raised, for dense operational work.',
    tokens: [
      color('--aegis-surface-base', 'Base'),
      color('--aegis-surface-canvas', 'Canvas'),
      color('--aegis-surface-elevated', 'Elevated'),
      color('--aegis-surface-panel', 'Panel'),
      color('--aegis-surface-rail', 'Rail'),
      color('--aegis-surface-overlay', 'Overlay'),
      color('--aegis-surface-raised', 'Raised'),
      color('--aegis-surface-hover', 'Hover'),
    ],
  },
  {
    id: 'text',
    title: 'Text',
    description: 'Foreground ramp from primary reading text down to faint hints.',
    tokens: [
      color('--aegis-text-primary', 'Primary'),
      color('--aegis-text-secondary', 'Secondary'),
      color('--aegis-text-muted', 'Muted'),
      color('--aegis-text-faint', 'Faint'),
      color('--aegis-text-inverse', 'Inverse'),
    ],
  },
  {
    id: 'accent',
    title: 'Operator accent',
    description: 'Cyan operator accents. State colours stay semantically reserved.',
    tokens: [
      color('--aegis-accent-cyan', 'Cyan'),
      color('--aegis-accent-strong', 'Strong'),
      color('--aegis-accent-soft', 'Soft'),
      color('--aegis-accent-line', 'Line'),
    ],
  },
  {
    id: 'risk',
    title: 'Risk bands',
    description: 'Risk severity scale used by metric tiles and scoring surfaces.',
    tokens: [
      color('--aegis-risk-low', 'Low'),
      color('--aegis-risk-medium', 'Medium'),
      color('--aegis-risk-high', 'High'),
      color('--aegis-risk-critical', 'Critical'),
    ],
  },
  {
    id: 'status',
    title: 'Status',
    description: 'NodeStatus plus connection/loading states. Meaning is fixed.',
    tokens: [
      color('--aegis-status-normal', 'Normal'),
      color('--aegis-status-suspicious', 'Suspicious'),
      color('--aegis-status-under-investigation', 'Under investigation'),
      color('--aegis-status-contained', 'Contained'),
      color('--aegis-status-compromised', 'Compromised'),
      color('--aegis-status-loading', 'Loading'),
      color('--aegis-status-error', 'Error'),
      color('--aegis-status-disconnected', 'Disconnected'),
      color('--aegis-status-empty', 'Empty'),
    ],
  },
  {
    id: 'borders',
    title: 'Borders & focus',
    description: 'Divider strokes and the focus ring used across interactive elements.',
    tokens: [
      color('--aegis-border-default', 'Default'),
      color('--aegis-border-subtle', 'Subtle'),
      color('--aegis-border-strong', 'Strong'),
      color('--aegis-focus-ring', 'Focus ring'),
    ],
  },
  {
    id: 'radii',
    title: 'Radii',
    description: 'Corner rounding scale for controls, panels, and dialogs.',
    tokens: [
      radius('--aegis-radius-sm', 'Small'),
      radius('--aegis-radius-md', 'Medium'),
      radius('--aegis-radius-lg', 'Large'),
      radius('--aegis-radius-xl', 'Extra large'),
    ],
  },
] as const;

/** Total number of tokens catalogued, used for the inspector summary. */
export function countTokens(groups: readonly TokenGroup[] = TOKEN_GROUPS): number {
  return groups.reduce((total, group) => total + group.tokens.length, 0);
}

/**
 * Read a token's resolved value from the given element (defaults to the
 * document root). Returns an empty string when unavailable (e.g. SSR).
 */
export function readTokenValue(name: string, element?: Element | null): string {
  if (typeof window === 'undefined') {
    return '';
  }
  const target = element ?? document.documentElement;
  return window.getComputedStyle(target).getPropertyValue(name).trim();
}

/** The `var(--token)` reference string authors paste into styles. */
export function tokenReference(name: string): string {
  return `var(${name})`;
}

/**
 * WCAG AA contrast acceptance for the §2.2 colour system, both themes.
 *
 * This suite reads the *actual* shipped token values from
 * `packages/ui/src/styles/tokens.css` (dark `:root` defaults + the
 * `:root[data-theme='light']` overrides) and computes real WCAG 2.1 contrast
 * ratios for every text/background and UI-component pairing described in §2.2
 * of the redesign spec. It is the deterministic, offline half of the §8
 * accessibility requirement ("run the light-theme pairs through the same
 * contrast check the a11y suite uses"): axe's own colour-contrast rule cannot
 * measure CSS-custom-property pairings under jsdom (no stylesheet cascade, and
 * the canvas is mocked in setup), so contrast is verified here against the
 * token source of truth and re-confirmed against rendered output in Chrome.
 *
 * Thresholds: 4.5:1 for normal-size text; 3:1 for large text and UI
 * components (focus ring, hairline accent borders, and the de-emphasized
 * `text-faint` tier, which is never used as body copy).
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

/**
 * Read the shipped token file verbatim so the ratios below are computed against
 * the exact values that render in the app. Read lazily (inside tests) rather
 * than at module top level: `import.meta.url` is a proper `file://` URL at test
 * runtime but not necessarily during Vite's transform of the module body.
 */
function readTokensCss(): string {
  const here = path.dirname(fileURLToPath(import.meta.url));
  return readFileSync(path.join(here, '../../src/styles/tokens.css'), 'utf8');
}

/** Extract the `{ ... }` body immediately following a selector. */
function selectorBlock(css: string, selector: string): string {
  const start = css.indexOf(selector);
  if (start === -1) {
    throw new Error(`selector not found in tokens.css: ${selector}`);
  }
  const open = css.indexOf('{', start);
  const close = css.indexOf('}', open);
  if (open === -1 || close === -1) {
    throw new Error(`malformed block for selector: ${selector}`);
  }
  return css.slice(open + 1, close);
}

/** Parse `--aegis-*: <value>;` declarations from a block into a name→value map. */
function parseVars(block: string): Record<string, string> {
  const vars: Record<string, string> = {};
  const re = /--([\w-]+)\s*:\s*([^;]+);/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(block)) !== null) {
    const name = match[1];
    const value = match[2];
    if (name === undefined || value === undefined) {
      continue;
    }
    vars[`--${name}`] = value.trim();
  }
  return vars;
}

type ThemeVars = Record<string, string>;
let themesCache: { dark: ThemeVars; light: ThemeVars } | null = null;

/** Parse both theme blocks from the token file (memoized, read lazily). */
function themeVars(theme: 'dark' | 'light'): ThemeVars {
  if (!themesCache) {
    const css = readTokensCss();
    const dark = parseVars(selectorBlock(css, ':root {'));
    const light = {
      ...dark,
      ...parseVars(selectorBlock(css, ":root[data-theme='light']")),
    };
    themesCache = { dark, light };
  }
  return themesCache[theme];
}

function channel(value: number): number {
  const s = value / 255;
  return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
}

function relativeLuminance(hex: string): number {
  const h = hex.replace('#', '');
  const full =
    h.length === 3
      ? h
          .split('')
          .map((c) => c + c)
          .join('')
      : h;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrastRatio(fg: string, bg: string): number {
  const l1 = relativeLuminance(fg);
  const l2 = relativeLuminance(bg);
  const hi = Math.max(l1, l2);
  const lo = Math.min(l1, l2);
  return (hi + 0.05) / (lo + 0.05);
}

const AA_TEXT = 4.5;
const AA_LARGE_UI = 3.0;

/** Surfaces on which body/label text is painted. */
const TEXT_SURFACES = [
  '--aegis-surface-base',
  '--aegis-surface-canvas',
  '--aegis-surface-elevated',
  '--aegis-surface-panel',
  '--aegis-surface-rail',
  '--aegis-surface-overlay',
  '--aegis-surface-raised',
  '--aegis-surface-hover',
] as const;

/** Content surfaces where the de-emphasized faint tier (empty placeholders) renders. */
const FAINT_SURFACES = [
  '--aegis-surface-base',
  '--aegis-surface-canvas',
  '--aegis-surface-elevated',
  '--aegis-surface-panel',
  '--aegis-surface-overlay',
  '--aegis-surface-raised',
] as const;

const ACCENT_TEXT_SURFACES = [
  '--aegis-surface-base',
  '--aegis-surface-canvas',
  '--aegis-surface-elevated',
  '--aegis-surface-panel',
  '--aegis-surface-rail',
] as const;

const FOCUS_SURFACES = [
  '--aegis-surface-base',
  '--aegis-surface-canvas',
  '--aegis-surface-elevated',
  '--aegis-surface-panel',
  '--aegis-surface-rail',
  '--aegis-surface-overlay',
] as const;

const RISK_BANDS = ['low', 'medium', 'high', 'critical'] as const;
const STATUSES = [
  'normal',
  'suspicious',
  'under-investigation',
  'contained',
  'compromised',
  'loading',
  'error',
  'disconnected',
  'empty',
] as const;

describe.each(['dark', 'light'] as const)('§2.2 colour contrast — %s theme', (theme) => {
  // Resolved lazily per call (memoized) so the token file is read at test
  // runtime, when `import.meta.url` is a resolvable file URL.
  const val = (name: string): string => {
    const raw = themeVars(theme)[name];
    if (!raw) {
      throw new Error(`token missing in ${theme}: ${name}`);
    }
    if (!raw.startsWith('#')) {
      throw new Error(`expected hex for ${name} in ${theme}, got: ${raw}`);
    }
    return raw;
  };

  it('normal text tiers meet AA (4.5:1) on every surface', () => {
    for (const tier of ['--aegis-text-primary', '--aegis-text-secondary', '--aegis-text-muted']) {
      for (const surface of TEXT_SURFACES) {
        const ratio = contrastRatio(val(tier), val(surface));
        expect(ratio, `${tier} on ${surface}`).toBeGreaterThanOrEqual(AA_TEXT);
      }
    }
  });

  it('de-emphasized faint tier meets the 3:1 large/UI floor on content surfaces', () => {
    for (const surface of FAINT_SURFACES) {
      const ratio = contrastRatio(val('--aegis-text-faint'), val(surface));
      expect(ratio, `--aegis-text-faint on ${surface}`).toBeGreaterThanOrEqual(AA_LARGE_UI);
    }
  });

  it('operator accent as text/link meets AA (4.5:1)', () => {
    for (const surface of ACCENT_TEXT_SURFACES) {
      expect(
        contrastRatio(val('--aegis-accent-cyan'), val(surface)),
        `--aegis-accent-cyan on ${surface}`,
      ).toBeGreaterThanOrEqual(AA_TEXT);
    }
    for (const surface of ['--aegis-surface-panel', '--aegis-surface-elevated']) {
      expect(
        contrastRatio(val('--aegis-accent-strong'), val(surface)),
        `--aegis-accent-strong on ${surface}`,
      ).toBeGreaterThanOrEqual(AA_TEXT);
    }
  });

  it('primary button label (text-inverse on accent) meets AA (4.5:1)', () => {
    expect(
      contrastRatio(val('--aegis-text-inverse'), val('--aegis-accent-cyan')),
    ).toBeGreaterThanOrEqual(AA_TEXT);
  });

  it('focus ring and hairline accent meet the 3:1 UI-component floor', () => {
    for (const surface of FOCUS_SURFACES) {
      expect(
        contrastRatio(val('--aegis-focus-ring'), val(surface)),
        `--aegis-focus-ring on ${surface}`,
      ).toBeGreaterThanOrEqual(AA_LARGE_UI);
    }
    expect(
      contrastRatio(val('--aegis-accent-line'), val('--aegis-surface-panel')),
      '--aegis-accent-line on --aegis-surface-panel',
    ).toBeGreaterThanOrEqual(AA_LARGE_UI);
  });

  it('risk-band chip text meets AA (4.5:1) on its band background', () => {
    for (const band of RISK_BANDS) {
      const ratio = contrastRatio(val(`--aegis-risk-${band}`), val(`--aegis-risk-${band}-bg`));
      expect(ratio, `risk ${band} fg/bg`).toBeGreaterThanOrEqual(AA_TEXT);
    }
  });

  it('status chip text meets AA (4.5:1) on its status background', () => {
    for (const status of STATUSES) {
      const ratio = contrastRatio(
        val(`--aegis-status-${status}`),
        val(`--aegis-status-${status}-bg`),
      );
      expect(ratio, `status ${status} fg/bg`).toBeGreaterThanOrEqual(AA_TEXT);
    }
  });
});

import { describe, expect, it } from 'vitest';

import {
  countTokens,
  readTokenValue,
  TOKEN_GROUPS,
  tokenReference,
} from '@/components/design-system/token-catalogue';

describe('token-catalogue', () => {
  it('exposes non-empty, uniquely named token groups', () => {
    expect(TOKEN_GROUPS.length).toBeGreaterThan(0);
    const ids = new Set(TOKEN_GROUPS.map((group) => group.id));
    expect(ids.size).toBe(TOKEN_GROUPS.length);
    for (const group of TOKEN_GROUPS) {
      expect(group.tokens.length).toBeGreaterThan(0);
    }
  });

  it('uses valid custom-property names', () => {
    for (const group of TOKEN_GROUPS) {
      for (const token of group.tokens) {
        expect(token.name.startsWith('--aegis-')).toBe(true);
        expect(token.label.length).toBeGreaterThan(0);
      }
    }
  });

  it('counts every catalogued token', () => {
    const manual = TOKEN_GROUPS.reduce((total, group) => total + group.tokens.length, 0);
    expect(countTokens()).toBe(manual);
  });

  it('builds a var() reference string', () => {
    expect(tokenReference('--aegis-accent-cyan')).toBe('var(--aegis-accent-cyan)');
  });

  it('reads a resolved value from a styled element', () => {
    const el = document.createElement('div');
    el.style.setProperty('--aegis-accent-cyan', '#59c9ea');
    document.body.appendChild(el);
    expect(readTokenValue('--aegis-accent-cyan', el)).toBe('#59c9ea');
    document.body.removeChild(el);
  });
});

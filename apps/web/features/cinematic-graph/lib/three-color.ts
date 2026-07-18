import * as THREE from 'three';

export interface ResolvedThreeColor {
  color: THREE.Color;
  opacity: number;
}

const DEFAULT_COLOR = '#64748b';
const resolvedColorCache = new Map<string, ResolvedThreeColor>();
const rgbaPattern = /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)$/i;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function byteToHex(value: number): string {
  return Math.round(clamp(value, 0, 255))
    .toString(16)
    .padStart(2, '0');
}

function normalizeHex(input: string): { hex: string; opacity: number } | null {
  const value = input.toLowerCase();
  if (/^#[0-9a-f]{3}$/.test(value)) {
    return {
      hex: `#${value.charAt(1)}${value.charAt(1)}${value.charAt(2)}${value.charAt(2)}${value.charAt(3)}${value.charAt(3)}`,
      opacity: 1,
    };
  }
  if (/^#[0-9a-f]{4}$/.test(value)) {
    return {
      hex: `#${value.charAt(1)}${value.charAt(1)}${value.charAt(2)}${value.charAt(2)}${value.charAt(3)}${value.charAt(3)}`,
      opacity: Number.parseInt(`${value.charAt(4)}${value.charAt(4)}`, 16) / 255,
    };
  }
  if (/^#[0-9a-f]{6}$/.test(value)) {
    return { hex: value, opacity: 1 };
  }
  if (/^#[0-9a-f]{8}$/.test(value)) {
    return {
      hex: value.slice(0, 7),
      opacity: Number.parseInt(value.slice(7, 9), 16) / 255,
    };
  }
  return null;
}

function normalizeColor(input: string, fallback: string): { hex: string; opacity: number } {
  const value = input.trim();
  if (value.toLowerCase() === 'transparent' || value.length === 0) {
    return { hex: normalizeHex(fallback)?.hex ?? DEFAULT_COLOR, opacity: 0 };
  }

  const hex = normalizeHex(value);
  if (hex) {
    return hex;
  }

  const rgba = value.match(rgbaPattern);
  if (rgba) {
    return {
      hex: `#${byteToHex(Number(rgba[1]))}${byteToHex(Number(rgba[2]))}${byteToHex(Number(rgba[3]))}`,
      opacity: rgba[4] === undefined ? 1 : clamp(Number(rgba[4]), 0, 1),
    };
  }

  return normalizeHex(fallback) ?? { hex: DEFAULT_COLOR, opacity: 1 };
}

export function resolveThreeColor(input: string, fallback = DEFAULT_COLOR): ResolvedThreeColor {
  const cacheKey = `${input.trim().toLowerCase()}|${fallback.trim().toLowerCase()}`;
  const cached = resolvedColorCache.get(cacheKey);
  if (cached) {
    return cached;
  }

  const normalized = normalizeColor(input, fallback);
  const resolved = {
    color: new THREE.Color(normalized.hex),
    opacity: normalized.opacity,
  };
  resolvedColorCache.set(cacheKey, resolved);
  return resolved;
}

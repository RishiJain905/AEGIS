import * as THREE from 'three';

/**
 * Canvas-painted sector nameplates for the bastion ring: uppercase,
 * letterspaced, flanked by thin rule lines — a war-table etching, not a DOM
 * overlay, so eight labels cost eight small textures and zero layout work.
 * Returns null outside a DOM (SSR / unit tests).
 */

const CANVAS_WIDTH = 512;
const CANVAS_HEIGHT = 96;

const cache = new Map<string, THREE.CanvasTexture>();

export function getZoneLabelTexture(label: string, tint = '#aebad0'): THREE.CanvasTexture | null {
  if (typeof document === 'undefined') {
    return null;
  }
  const key = `${tint}:${label}`;
  const cached = cache.get(key);
  if (cached) {
    return cached;
  }

  const canvas = document.createElement('canvas');
  canvas.width = CANVAS_WIDTH;
  canvas.height = CANVAS_HEIGHT;
  const context = canvas.getContext('2d');
  if (!context) {
    return null;
  }

  context.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
  context.font = '600 34px ui-monospace, "Cascadia Mono", "Segoe UI Mono", monospace';
  context.textAlign = 'center';
  context.textBaseline = 'middle';

  const text = label.toUpperCase();
  // Manual letterspacing: canvas has no reliable cross-browser CSS tracking.
  // Grapheme segmentation keeps non-ASCII labels intact.
  const tracking = 6;
  const graphemes = [...new Intl.Segmenter().segment(text)].map((entry) => entry.segment);
  const widths = graphemes.map((char) => context.measureText(char).width);
  const total = widths.reduce((sum, width) => sum + width + tracking, -tracking);
  const scale = total > CANVAS_WIDTH - 96 ? (CANVAS_WIDTH - 96) / total : 1;

  context.save();
  context.translate(CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2);
  context.scale(scale, scale);
  context.fillStyle = tint;
  let cursor = -total / 2;
  graphemes.forEach((char, index) => {
    const width = widths[index] ?? 0;
    context.fillText(char, cursor + width / 2, 0);
    cursor += width + tracking;
  });
  context.restore();

  // Flanking rules give the nameplate its etched, instrument-panel read.
  const ruleY = CANVAS_HEIGHT / 2;
  const ruleInset = 12;
  const ruleLength = Math.max(24, (CANVAS_WIDTH - total * scale) / 2 - 40);
  context.strokeStyle = `${tint}66`;
  context.lineWidth = 2;
  context.beginPath();
  context.moveTo(ruleInset, ruleY);
  context.lineTo(ruleInset + ruleLength, ruleY);
  context.moveTo(CANVAS_WIDTH - ruleInset, ruleY);
  context.lineTo(CANVAS_WIDTH - ruleInset - ruleLength, ruleY);
  context.stroke();

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  cache.set(key, texture);
  return texture;
}

import * as THREE from 'three';

import { drawShape } from '@/features/operational-graph/rendering/aegis-canvas-renderers';
import type { NodeGlyphShape } from '@/features/operational-graph/semantic/graph-semantic-styles';

const TEXTURE_SIZE = 96;

const textureCache = new Map<NodeGlyphShape, THREE.CanvasTexture>();

/**
 * §7.2 billboard glyph textures: one small canvas texture per asset-type
 * shape, drawn with the same `drawShape` painter the 2D canvas renderers use,
 * so an operator who learned the 2D legend recognizes the same glyphs in 3D.
 * Textures are created lazily on the client and cached for the session.
 */
export function getGlyphTexture(shape: NodeGlyphShape): THREE.CanvasTexture | null {
  const cached = textureCache.get(shape);
  if (cached) {
    return cached;
  }
  if (typeof document === 'undefined') {
    return null;
  }
  const canvas = document.createElement('canvas');
  canvas.width = TEXTURE_SIZE;
  canvas.height = TEXTURE_SIZE;
  const context = canvas.getContext('2d');
  if (!context) {
    return null;
  }

  const center = TEXTURE_SIZE / 2;
  const radius = TEXTURE_SIZE * 0.32;
  context.clearRect(0, 0, TEXTURE_SIZE, TEXTURE_SIZE);
  // Near-white glyph with a dark rim so it stays legible over any node tint.
  drawShape(context, shape, center, center, radius);
  context.fillStyle = 'rgba(234, 244, 250, 0.96)';
  context.fill();
  context.strokeStyle = 'rgba(6, 14, 20, 0.85)';
  context.lineWidth = TEXTURE_SIZE * 0.055;
  context.stroke();

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 2;
  textureCache.set(shape, texture);
  return texture;
}

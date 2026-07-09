/**
 * Local reviewed fragment helpers for risk-halo tinting.
 * No remote shader loading or untrusted code generation.
 */
export const RISK_HALO_VERTEX = /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

export const RISK_HALO_FRAGMENT = /* glsl */ `
uniform vec3 uColor;
uniform float uOpacity;
varying vec2 vUv;
void main() {
  float dist = distance(vUv, vec2(0.5));
  float alpha = smoothstep(0.5, 0.2, dist) * uOpacity;
  gl_FragColor = vec4(uColor, alpha);
}
`;

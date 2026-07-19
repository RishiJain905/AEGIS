/**
 * Custom Sigma edge programs implementing the "alive edges" treatment
 * (redesign spec §7.9) plus the dashed incident-containment read (§7.4).
 *
 * The GLSL below is local and reviewed — adapted from sigma@3.0.2's MIT
 * edge-rectangle / edge-clamped programs (node_modules/sigma/dist), extended
 * with a travelling-brightness flow wave and a static dash pattern. No remote
 * shader loading.
 *
 * Animation contract (spec §7.9 performance rules):
 * - One shared clock uniform (`u_time`) drives every edge; per-edge variation
 *   comes from attributes uploaded only when the graph data itself changes.
 * - The per-frame cost is exactly one `Sigma.scheduleRender()` — no geometry
 *   rebuild, no attribute re-upload, no React re-render, no allocation.
 * - Reduced motion / LOW tier freeze the clock AND zero the flow gate, so
 *   edges render fully static (semantic color/weight/dash only).
 */
import type { Attributes } from 'graphology-types';
import {
  EdgeArrowHeadProgram,
  EdgeProgram,
  createEdgeCompoundProgram,
  DEFAULT_EDGE_ARROW_HEAD_PROGRAM_OPTIONS,
  type EdgeProgramType,
  type InstancedProgramDefinition,
  type ProgramInfo,
} from 'sigma/rendering';
import type { EdgeDisplayData, NodeDisplayData, RenderParams } from 'sigma/types';
import { floatColor } from 'sigma/utils';

import { getGraphAnimationTime, NO_PULSE } from '../semantic/edge-activity';
import type { EdgeFlowProfile } from '../semantic/graph-semantic-styles';

// GL constants inlined so this module never touches the global
// `WebGLRenderingContext` at import time (absent under jsdom).
const GL_FLOAT = 0x1406;
const GL_UNSIGNED_BYTE = 0x1401;
const GL_TRIANGLES = 0x0004;

/** Display-data attributes the Sigma adapter writes per edge. */
export interface AliveEdgeDisplayAttributes {
  /** Flow cycles/sec; 0 disables the travelling wave for this edge. */
  flowSpeed?: number;
  /** 0..1 brightness amplitude of the travelling wave. */
  flowAmplitude?: number;
  /** 1 renders the §7.4 dashed containment pattern; 0 solid. */
  dashFlag?: number;
  /** Shared-clock timestamp of the edge's last live-event pulse (NO_PULSE if
   * never pulsed). */
  pulseAt?: number;
  /** Deterministic phase offset in [0, 1). */
  flowPhase?: number;
}

/** Module-level render state read by `setUniforms` each frame. Mutating it
 * costs nothing until the next render — the flow driver loop (or any Sigma
 * refresh) picks it up via uniforms without touching edge attributes. */
const flowRenderState = { profile: 'full' as EdgeFlowProfile };

export function setAliveEdgeFlowProfile(profile: EdgeFlowProfile): void {
  flowRenderState.profile = profile;
}

export function getAliveEdgeFlowProfile(): EdgeFlowProfile {
  return flowRenderState.profile;
}

const UNIFORMS = [
  'u_matrix',
  'u_zoomRatio',
  'u_sizeRatio',
  'u_correctionRatio',
  'u_pixelRatio',
  'u_feather',
  'u_minEdgeThickness',
  'u_lengthToThicknessRatio',
  'u_dimensions',
  'u_time',
  'u_flowEnabled',
  'u_phaseScale',
] as const;

type AliveEdgeUniform = (typeof UNIFORMS)[number];

function buildVertexShader(withArrowClamp: boolean): string {
  return /* glsl */ `
attribute vec4 a_id;
attribute vec4 a_color;
attribute vec2 a_normal;
attribute float a_normalCoef;
attribute vec2 a_positionStart;
attribute vec2 a_positionEnd;
attribute float a_positionCoef;
${withArrowClamp ? 'attribute float a_radius;\nattribute float a_radiusCoef;' : ''}
attribute vec2 a_flow;
attribute float a_dash;
attribute float a_pulse;
attribute float a_phase;

uniform mat3 u_matrix;
uniform float u_zoomRatio;
uniform float u_sizeRatio;
uniform float u_pixelRatio;
uniform float u_correctionRatio;
uniform float u_feather;
uniform float u_minEdgeThickness;
${withArrowClamp ? 'uniform float u_lengthToThicknessRatio;' : ''}
uniform vec2 u_dimensions;
uniform float u_phaseScale;

varying vec4 v_color;
varying vec2 v_normal;
varying float v_thickness;
varying float v_feather;
varying float v_coef;
varying float v_lenPx;
varying vec2 v_flow;
varying float v_dash;
varying float v_pulse;
varying float v_phase;

const float bias = 255.0 / 254.0;

void main() {
  float minThickness = u_minEdgeThickness;

  vec2 normal = a_normal * a_normalCoef;
  vec2 position = a_positionStart * (1.0 - a_positionCoef) + a_positionEnd * a_positionCoef;

  float normalLength = length(normal);
  vec2 unitNormal = normal / normalLength;

  // Same thickness math as sigma's stock edge programs:
  float pixelsThickness = max(normalLength, minThickness * u_sizeRatio);
  float webGLThickness = pixelsThickness * u_correctionRatio / u_sizeRatio;

${
  withArrowClamp
    ? `  // Shorten the shaft to leave space for the arrow head (edge-clamped):
  float radius = a_radius * a_radiusCoef;
  float direction = sign(radius);
  float webGLNodeRadius = direction * radius * 2.0 * u_correctionRatio / u_sizeRatio;
  float webGLArrowHeadLength = webGLThickness * u_lengthToThicknessRatio * 2.0;
  vec2 compensationVector =
    vec2(-direction * unitNormal.y, direction * unitNormal.x) * (webGLNodeRadius + webGLArrowHeadLength);
  gl_Position = vec4((u_matrix * vec3(position + unitNormal * webGLThickness + compensationVector, 1)).xy, 0, 1);`
    : `  gl_Position = vec4((u_matrix * vec3(position + unitNormal * webGLThickness, 1)).xy, 0, 1);`
}

  v_thickness = webGLThickness / u_zoomRatio;
  v_normal = unitNormal;
  v_feather = u_feather * u_correctionRatio / u_zoomRatio / u_pixelRatio * 2.0;

  // Screen-space length of the edge, for zoom-stable dash/flow wavelengths.
  vec2 startPx = (u_matrix * vec3(a_positionStart, 1)).xy * 0.5 * u_dimensions;
  vec2 endPx = (u_matrix * vec3(a_positionEnd, 1)).xy * 0.5 * u_dimensions;
  v_lenPx = length(endPx - startPx);

  v_coef = a_positionCoef;
  v_flow = a_flow;
  v_dash = a_dash;
  v_pulse = a_pulse;
  v_phase = a_phase * u_phaseScale;

  #ifdef PICKING_MODE
  v_color = a_id;
  #else
  v_color = a_color;
  #endif

  v_color.a *= bias;
}
`;
}

const FRAGMENT_SHADER_SOURCE = /* glsl */ `
precision mediump float;

varying vec4 v_color;
varying vec2 v_normal;
varying float v_thickness;
varying float v_feather;
varying float v_coef;
varying float v_lenPx;
varying vec2 v_flow;
varying float v_dash;
varying float v_pulse;
varying float v_phase;

uniform float u_time;
uniform float u_flowEnabled;

const vec4 transparent = vec4(0.0, 0.0, 0.0, 0.0);
const float DASH_PERIOD_PX = 12.0;
const float FLOW_WAVELENGTH_PX = 96.0;

void main(void) {
  #ifdef PICKING_MODE
  // Picking stays solid — dash gaps and flow troughs remain clickable.
  gl_FragColor = v_color;
  #else
  float dist = length(v_normal) * v_thickness;
  float t = smoothstep(v_thickness - v_feather, v_thickness, dist);

  vec4 color = v_color;
  float px = v_coef * v_lenPx;

  // §7.4 incident-scope containment: static literal dash (never animated).
  if (v_dash > 0.5) {
    float m = fract(px / DASH_PERIOD_PX);
    float dashA = 1.0 - smoothstep(0.52, 0.62, m);
    color *= mix(0.16, 1.0, dashA);
  }

  // §7.9 alive flow: a travelling brightness segment moving source → target.
  // Gated by u_flowEnabled (reduced motion / LOW tier => 0 => fully static).
  if (u_flowEnabled > 0.5) {
    float pulseBoost = 0.0;
    if (v_pulse > -100000.0) {
      pulseBoost = exp(-max(u_time - v_pulse, 0.0) * 1.3);
    }
    float amp = clamp(v_flow.y + pulseBoost * 0.9, 0.0, 1.0);
    if (amp > 0.004 && v_lenPx > 1.0) {
      float w = fract(px / FLOW_WAVELENGTH_PX - u_time * v_flow.x - v_phase);
      float bump = smoothstep(0.0, 0.3, w) * (1.0 - smoothstep(0.42, 0.85, w));
      // Premultiplied-alpha-safe: brighten rgb only.
      color.rgb = mix(color.rgb, vec3(1.0), amp * bump * 0.6);
    }
  }

  gl_FragColor = mix(color, transparent, t);
  #endif
}
`;

interface AliveEdgeProgramOptions {
  withArrowClamp: boolean;
  lengthToThicknessRatio: number;
}

function createAliveEdgeProgramClass<
  N extends Attributes = Attributes,
  E extends Attributes = Attributes,
  G extends Attributes = Attributes,
>(options: AliveEdgeProgramOptions): EdgeProgramType<N, E, G> {
  const { withArrowClamp, lengthToThicknessRatio } = options;

  return class AliveEdgeProgram extends EdgeProgram<AliveEdgeUniform, N, E, G> {
    getDefinition(): InstancedProgramDefinition<AliveEdgeUniform> {
      return {
        VERTICES: 6,
        VERTEX_SHADER_SOURCE: buildVertexShader(withArrowClamp),
        FRAGMENT_SHADER_SOURCE,
        METHOD: GL_TRIANGLES,
        UNIFORMS,
        ATTRIBUTES: [
          { name: 'a_positionStart', size: 2, type: GL_FLOAT },
          { name: 'a_positionEnd', size: 2, type: GL_FLOAT },
          { name: 'a_normal', size: 2, type: GL_FLOAT },
          { name: 'a_color', size: 4, type: GL_UNSIGNED_BYTE, normalized: true },
          { name: 'a_id', size: 4, type: GL_UNSIGNED_BYTE, normalized: true },
          ...(withArrowClamp ? [{ name: 'a_radius', size: 1, type: GL_FLOAT }] : []),
          { name: 'a_flow', size: 2, type: GL_FLOAT },
          { name: 'a_dash', size: 1, type: GL_FLOAT },
          { name: 'a_pulse', size: 1, type: GL_FLOAT },
          { name: 'a_phase', size: 1, type: GL_FLOAT },
        ],
        CONSTANT_ATTRIBUTES: [
          // a_positionCoef: 0 => a_positionStart, 1 => a_positionEnd.
          { name: 'a_positionCoef', size: 1, type: GL_FLOAT },
          { name: 'a_normalCoef', size: 1, type: GL_FLOAT },
          ...(withArrowClamp ? [{ name: 'a_radiusCoef', size: 1, type: GL_FLOAT }] : []),
        ],
        CONSTANT_DATA: withArrowClamp
          ? [
              [0, 1, 0],
              [0, -1, 0],
              [1, 1, 1],
              [1, 1, 1],
              [0, -1, 0],
              [1, -1, -1],
            ]
          : [
              [0, 1],
              [0, -1],
              [1, 1],
              [1, 1],
              [0, -1],
              [1, -1],
            ],
      };
    }

    processVisibleItem(
      edgeIndex: number,
      startIndex: number,
      sourceData: NodeDisplayData,
      targetData: NodeDisplayData,
      data: EdgeDisplayData,
    ): void {
      const alive = data as EdgeDisplayData & AliveEdgeDisplayAttributes;
      const thickness = data.size || 1;
      const x1 = sourceData.x;
      const y1 = sourceData.y;
      const x2 = targetData.x;
      const y2 = targetData.y;
      const color = floatColor(data.color);

      const dx = x2 - x1;
      const dy = y2 - y1;
      let len = dx * dx + dy * dy;
      let n1 = 0;
      let n2 = 0;
      if (len) {
        len = 1 / Math.sqrt(len);
        n1 = -dy * len * thickness;
        n2 = dx * len * thickness;
      }

      const array = this.array;
      let index = startIndex;
      array[index++] = x1;
      array[index++] = y1;
      array[index++] = x2;
      array[index++] = y2;
      array[index++] = n1;
      array[index++] = n2;
      array[index++] = color;
      array[index++] = edgeIndex;
      if (withArrowClamp) {
        array[index++] = targetData.size || 1;
      }
      array[index++] = alive.flowSpeed ?? 0;
      array[index++] = alive.flowAmplitude ?? 0;
      array[index++] = alive.dashFlag ?? 0;
      array[index++] = alive.pulseAt ?? NO_PULSE;
      array[index++] = alive.flowPhase ?? 0;
    }

    setUniforms(params: RenderParams, { gl, uniformLocations }: ProgramInfo): void {
      const location = (name: AliveEdgeUniform): WebGLUniformLocation | null =>
        uniformLocations[name] ?? null;
      const flowEnabled = flowRenderState.profile !== 'static';
      gl.uniformMatrix3fv(location('u_matrix'), false, params.matrix);
      gl.uniform1f(location('u_zoomRatio'), params.zoomRatio);
      gl.uniform1f(location('u_sizeRatio'), params.sizeRatio);
      gl.uniform1f(location('u_correctionRatio'), params.correctionRatio);
      gl.uniform1f(location('u_pixelRatio'), params.pixelRatio);
      gl.uniform1f(location('u_feather'), params.antiAliasingFeather);
      gl.uniform1f(location('u_minEdgeThickness'), params.minEdgeThickness);
      if (withArrowClamp) {
        gl.uniform1f(location('u_lengthToThicknessRatio'), lengthToThicknessRatio);
      }
      gl.uniform2f(location('u_dimensions'), params.width, params.height);
      // Frozen clock + closed gate when static: edges cannot move even if a
      // stray refresh happens; 'coarse' collapses all phases to one (§7.9
      // MEDIUM: shared-phase variant).
      gl.uniform1f(location('u_time'), flowEnabled ? getGraphAnimationTime() : 0);
      gl.uniform1f(location('u_flowEnabled'), flowEnabled ? 1 : 0);
      gl.uniform1f(location('u_phaseScale'), flowRenderState.profile === 'full' ? 1 : 0);
    }
  };
}

/** Replacement for the stock 'line' edge program (undirected / low-confidence
 * edges): flat rectangle shaft + alive-flow support. */
export const AliveEdgeLineProgram: EdgeProgramType = createAliveEdgeProgramClass({
  withArrowClamp: false,
  lengthToThicknessRatio: DEFAULT_EDGE_ARROW_HEAD_PROGRAM_OPTIONS.lengthToThicknessRatio,
});

/** Replacement for the stock 'arrow' edge program (directed edges): clamped
 * alive shaft + sigma's stock arrow head. */
export const AliveEdgeArrowProgram: EdgeProgramType = createEdgeCompoundProgram([
  createAliveEdgeProgramClass({
    withArrowClamp: true,
    lengthToThicknessRatio: DEFAULT_EDGE_ARROW_HEAD_PROGRAM_OPTIONS.lengthToThicknessRatio,
  }),
  EdgeArrowHeadProgram,
]);

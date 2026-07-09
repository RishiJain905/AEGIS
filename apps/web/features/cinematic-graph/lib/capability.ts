import {
  RenderQualityTier,
  type CapabilityReport,
  type RenderQualityTierValue,
} from '../contracts';

const DEFAULT_DPR_CAP = 1.75;
const LOW_MEMORY_GB = 4;
const MEDIUM_MEMORY_GB = 8;

export interface ProbeCapabilityOptions {
  reducedMotion?: boolean;
  forceWebglUnavailable?: boolean;
  estimatedDeviceMemoryGb?: number | null;
  devicePixelRatio?: number;
}

function readDeviceMemoryGb(): number | null {
  if (typeof navigator === 'undefined') {
    return null;
  }
  const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
  return typeof memory === 'number' && Number.isFinite(memory) ? memory : null;
}

function probeWebgl(): {
  webglAvailable: boolean;
  webgl2Available: boolean;
  maxTextureSize: number;
} {
  if (typeof document === 'undefined') {
    return { webglAvailable: false, webgl2Available: false, maxTextureSize: 0 };
  }
  try {
    const canvas = document.createElement('canvas');
    // jsdom throws "Not implemented" via console rather than a catchable error.
    const originalGetContext = canvas.getContext.bind(canvas);
    let gl2: WebGL2RenderingContext | null = null;
    let gl: WebGLRenderingContext | null = null;
    try {
      gl2 = originalGetContext('webgl2') as WebGL2RenderingContext | null;
    } catch {
      gl2 = null;
    }
    if (gl2 && typeof (gl2 as WebGL2RenderingContext).getParameter === 'function') {
      const maxTextureSize = gl2.getParameter(gl2.MAX_TEXTURE_SIZE) as number;
      const lose = gl2.getExtension('WEBGL_lose_context');
      lose?.loseContext();
      return {
        webglAvailable: true,
        webgl2Available: true,
        maxTextureSize: typeof maxTextureSize === 'number' ? maxTextureSize : 0,
      };
    }
    try {
      gl =
        (originalGetContext('webgl') as WebGLRenderingContext | null) ??
        (originalGetContext('experimental-webgl') as WebGLRenderingContext | null);
    } catch {
      gl = null;
    }
    if (gl && typeof gl.getParameter === 'function') {
      const maxTextureSize = gl.getParameter(gl.MAX_TEXTURE_SIZE) as number;
      const lose = gl.getExtension('WEBGL_lose_context');
      lose?.loseContext();
      return {
        webglAvailable: true,
        webgl2Available: false,
        maxTextureSize: typeof maxTextureSize === 'number' ? maxTextureSize : 0,
      };
    }
  } catch {
    return { webglAvailable: false, webgl2Available: false, maxTextureSize: 0 };
  }
  return { webglAvailable: false, webgl2Available: false, maxTextureSize: 0 };
}

export function recommendQualityTier(input: {
  webglAvailable: boolean;
  reducedMotion: boolean;
  estimatedDeviceMemoryGb: number | null;
}): { tier: RenderQualityTierValue; reasonCodes: string[] } {
  const reasonCodes: string[] = [];
  if (!input.webglAvailable) {
    reasonCodes.push('webgl-unavailable');
    return { tier: RenderQualityTier.FALLBACK_2D, reasonCodes };
  }
  if (input.reducedMotion) {
    reasonCodes.push('reduced-motion');
  }
  const memory = input.estimatedDeviceMemoryGb;
  if (memory !== null && memory <= LOW_MEMORY_GB) {
    reasonCodes.push('low-device-memory');
    return { tier: RenderQualityTier.LOW, reasonCodes };
  }
  if (memory !== null && memory <= MEDIUM_MEMORY_GB) {
    reasonCodes.push('medium-device-memory');
    return { tier: RenderQualityTier.MEDIUM, reasonCodes };
  }
  if (input.reducedMotion) {
    return { tier: RenderQualityTier.MEDIUM, reasonCodes };
  }
  return { tier: RenderQualityTier.HIGH, reasonCodes };
}

export function probeCapabilityReport(
  options: ProbeCapabilityOptions = {},
): CapabilityReport {
  const reducedMotion = options.reducedMotion ?? false;
  const estimatedDeviceMemoryGb =
    options.estimatedDeviceMemoryGb === undefined
      ? readDeviceMemoryGb()
      : options.estimatedDeviceMemoryGb;
  const webgl = options.forceWebglUnavailable
    ? { webglAvailable: false, webgl2Available: false, maxTextureSize: 0 }
    : probeWebgl();
  const recommendation = recommendQualityTier({
    webglAvailable: webgl.webglAvailable,
    reducedMotion,
    estimatedDeviceMemoryGb,
  });
  const dpr =
    options.devicePixelRatio ??
    (typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1);

  return {
    schemaVersion: 1,
    webglAvailable: webgl.webglAvailable,
    webgl2Available: webgl.webgl2Available,
    maxTextureSize: webgl.maxTextureSize,
    devicePixelRatioCap: Math.min(DEFAULT_DPR_CAP, Math.max(1, dpr)),
    reducedMotion,
    recommendedTier: recommendation.tier,
    reasonCodes: recommendation.reasonCodes,
    estimatedDeviceMemoryGb,
  };
}

export function dprForTier(tier: RenderQualityTierValue, cap: number): number {
  switch (tier) {
    case RenderQualityTier.HIGH:
      return Math.min(cap, 1.75);
    case RenderQualityTier.MEDIUM:
      return Math.min(cap, 1.25);
    case RenderQualityTier.LOW:
      return 1;
    case RenderQualityTier.FALLBACK_2D:
      return 1;
    default: {
      const _exhaustive: never = tier;
      throw new Error(`Unhandled render quality tier: ${String(_exhaustive)}`);
    }
  }
}

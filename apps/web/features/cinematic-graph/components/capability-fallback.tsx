'use client';

import { Alert } from '@aegis/ui';

interface CapabilityFallbackProps {
  reasonCodes: string[];
  onReturnTo2d: () => void;
}

export function CapabilityFallbackNotice({
  reasonCodes,
  onReturnTo2d,
}: CapabilityFallbackProps) {
  return (
    <Alert
      variant="warning"
      title="3D semantic view unavailable"
      className="mb-3"
      data-testid="cinematic-capability-fallback"
    >
      <p className="mb-2 text-sm">
        This device cannot run the Three.js semantic renderer. The Sigma.js 2D operational graph
        remains the primary investigation surface.
      </p>
      {reasonCodes.length > 0 ? (
        <p className="mb-2 font-mono text-xs" data-testid="cinematic-fallback-reasons">
          {reasonCodes.join(', ')}
        </p>
      ) : null}
      <button
        type="button"
        className="rounded border border-[var(--aegis-border)] px-2 py-1 text-xs"
        data-testid="cinematic-return-2d"
        onClick={onReturnTo2d}
      >
        Continue in 2D
      </button>
    </Alert>
  );
}

import { create } from 'zustand';

import { nudgeCompositorAfterModeSwitch } from '../lib/compositor-nudge';
import { GraphViewMode, type GraphViewModeValue } from '../contracts/graph-view-mode';
import { defaultCameraBookmark3D, type CameraBookmark3D } from '../contracts/camera-bookmark-3d';
import { defaultCapabilityReport, type CapabilityReport } from '../contracts/capability-report';
import { RenderQualityTier, type RenderQualityTierValue } from '../contracts/render-quality-tier';

export interface CinematicGraphUiState {
  viewMode: GraphViewModeValue;
  capability: CapabilityReport;
  qualityTier: RenderQualityTierValue;
  camera: CameraBookmark3D;
  lastError: { code: string; message: string } | null;
  setViewMode: (mode: GraphViewModeValue) => void;
  setCapability: (report: CapabilityReport) => void;
  setQualityTier: (tier: RenderQualityTierValue) => void;
  setCamera: (bookmark: CameraBookmark3D) => void;
  setLastError: (error: { code: string; message: string } | null) => void;
  reset: () => void;
}

const initialState = {
  viewMode: GraphViewMode.TWO_D as GraphViewModeValue,
  capability: defaultCapabilityReport,
  qualityTier: RenderQualityTier.FALLBACK_2D as RenderQualityTierValue,
  camera: defaultCameraBookmark3D,
  lastError: null as { code: string; message: string } | null,
};

export const useCinematicGraphStore = create<CinematicGraphUiState>((set) => ({
  ...initialState,
  setViewMode: (mode) => {
    set((state) => {
      if (state.viewMode !== mode) {
        nudgeCompositorAfterModeSwitch();
      }
      return { viewMode: mode };
    });
  },
  setCapability: (report) => {
    set((state) => ({
      capability: report,
      qualityTier: report.recommendedTier,
      // Do not force viewMode here — only disable 3D entry when WebGL is unavailable.
      // Operators may still open 3D to see the fallback notice when probing is inconclusive.
      viewMode: state.viewMode,
    }));
  },
  setQualityTier: (tier) => {
    set({ qualityTier: tier });
  },
  setCamera: (bookmark) => {
    set({ camera: bookmark });
  },
  setLastError: (error) => {
    set({ lastError: error });
  },
  reset: () => {
    set({ ...initialState });
  },
}));

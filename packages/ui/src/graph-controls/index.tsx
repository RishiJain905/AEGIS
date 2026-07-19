'use client';

import { cn } from '../lib/cn';
import { Button } from '../primitives/button';

export interface GraphSearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  'data-testid'?: string;
}

export function GraphSearchInput({
  value,
  onChange,
  placeholder = 'Search nodes by label or ID…',
  className,
  'data-testid': testId = 'graph-search-input',
}: GraphSearchInputProps) {
  return (
    <input
      type="search"
      role="searchbox"
      aria-label="Search graph nodes"
      data-testid={testId}
      value={value}
      onChange={(event) => {
        onChange(event.target.value);
      }}
      placeholder={placeholder}
      className={cn(
        'min-h-10 w-full rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-canvas)] px-3 py-2 text-sm text-[var(--aegis-text-primary)] shadow-[inset_0_1px_5px_rgb(0_0_0_/_0.24)] placeholder:text-[var(--aegis-text-muted)] focus-visible:border-[var(--aegis-accent-line)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--aegis-focus-ring)]',
        className,
      )}
    />
  );
}

export interface GraphLayerOption {
  id: string;
  label: string;
}

export interface GraphLayerControlsProps {
  layers: GraphLayerOption[];
  enabledLayers: string[];
  onToggle: (layerId: string) => void;
  className?: string;
}

export function GraphLayerControls({
  layers,
  enabledLayers,
  onToggle,
  className,
}: GraphLayerControlsProps) {
  return (
    <div
      className={cn('flex flex-wrap gap-1', className)}
      role="group"
      aria-label="Graph layer filters"
      data-testid="graph-layer-controls"
    >
      {layers.map((layer) => {
        const active = enabledLayers.includes(layer.id);
        return (
          <Button
            key={layer.id}
            variant={active ? 'default' : 'outline'}
            size="sm"
            data-testid={`graph-layer-${layer.id}`}
            aria-pressed={active}
            onClick={() => {
              onToggle(layer.id);
            }}
          >
            {layer.label}
          </Button>
        );
      })}
    </div>
  );
}

export interface GraphLegendItem {
  label: string;
  color: string;
  description?: string;
  shape?: 'circle' | 'diamond' | 'square' | 'triangle' | 'hexagon' | 'line' | 'ring';
}

export interface GraphLegendProps {
  title?: string;
  items: GraphLegendItem[];
  className?: string;
}

export function GraphLegend({ title = 'Legend', items, className }: GraphLegendProps) {
  return (
    <div
      className={cn(
        'rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[linear-gradient(145deg,var(--aegis-surface-raised),var(--aegis-surface-elevated))] p-3 shadow-[var(--aegis-shadow-control)]',
        className,
      )}
      data-testid="graph-legend"
      aria-label={title}
    >
      <p className="mb-3 font-[family-name:var(--aegis-font-display)] text-[0.6875rem] font-semibold uppercase tracking-[0.09em] text-[var(--aegis-text-muted)]">
        {title}
      </p>
      <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
        {items.map((item) => {
          const shape = item.shape ?? 'circle';
          const slug = item.label
            .toLowerCase()
            .replaceAll(/[^a-z0-9]+/g, '-')
            .replaceAll(/^-|-$/g, '');
          return (
            <li key={item.label} className="flex min-w-0 items-center gap-2.5 text-xs">
              <span
                className={cn(
                  'inline-block h-3.5 w-3.5 shrink-0 shadow-[0_0_10px_currentColor]',
                  shape === 'circle' && 'rounded-full',
                  shape === 'diamond' && 'rotate-45 rounded-[2px]',
                  shape === 'square' && 'rounded-[2px]',
                  shape === 'triangle' && '[clip-path:polygon(50%_0,100%_100%,0_100%)]',
                  shape === 'hexagon' &&
                    '[clip-path:polygon(25%_0,75%_0,100%_50%,75%_100%,25%_100%,0_50%)]',
                  shape === 'line' && 'h-0.5 w-5 rounded-full',
                  shape === 'ring' && 'rounded-full border-2 bg-transparent',
                )}
                style={
                  shape === 'ring' ? { borderColor: item.color } : { backgroundColor: item.color }
                }
                aria-hidden="true"
                data-shape={shape}
                data-testid={`graph-legend-symbol-${slug}`}
              />
              <span className="min-w-0">
                <span className="block font-medium text-[var(--aegis-text-primary)]">
                  {item.label}
                </span>
                {item.description ? (
                  <span className="block text-[11px] leading-4 text-[var(--aegis-text-muted)]">
                    {item.description}
                  </span>
                ) : null}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export interface GraphCameraControlsProps {
  onFit: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  className?: string;
}

export function GraphCameraControls({
  onFit,
  onZoomIn,
  onZoomOut,
  onReset,
  className,
}: GraphCameraControlsProps) {
  return (
    <div
      className={cn('flex flex-wrap gap-1', className)}
      role="group"
      aria-label="Graph camera controls"
      data-testid="graph-camera-controls"
    >
      <Button variant="outline" size="sm" onClick={onFit} data-testid="graph-fit">
        Fit
      </Button>
      <Button variant="outline" size="sm" onClick={onZoomIn} aria-label="Zoom in">
        +
      </Button>
      <Button variant="outline" size="sm" onClick={onZoomOut} aria-label="Zoom out">
        −
      </Button>
      <Button variant="outline" size="sm" onClick={onReset} data-testid="graph-reset-camera">
        Reset
      </Button>
    </div>
  );
}

export interface GraphIsolationControlsProps {
  isolationActive: boolean;
  onIsolate: () => void;
  onRestore: () => void;
  disabled?: boolean;
  className?: string;
}

export function GraphIsolationControls({
  isolationActive,
  onIsolate,
  onRestore,
  disabled = false,
  className,
}: GraphIsolationControlsProps) {
  return (
    <div
      className={cn('flex flex-wrap gap-1', className)}
      role="group"
      aria-label="Graph isolation controls"
      data-testid="graph-isolation-controls"
    >
      <Button
        variant={isolationActive ? 'default' : 'outline'}
        size="sm"
        disabled={disabled}
        data-testid="graph-isolate-neighborhood"
        onClick={onIsolate}
      >
        Isolate neighborhood
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={!isolationActive}
        data-testid="graph-restore-full"
        onClick={onRestore}
      >
        Restore full graph
      </Button>
    </div>
  );
}

export interface GraphOverlayToggleProps {
  toggles: {
    risk: boolean;
    status: boolean;
    evidence: boolean;
    incident: boolean;
  };
  onToggle: (key: 'risk' | 'status' | 'evidence' | 'incident') => void;
  className?: string;
}

export function GraphOverlayToggle({ toggles, onToggle, className }: GraphOverlayToggleProps) {
  const items: {
    key: 'risk' | 'status' | 'evidence' | 'incident';
    label: string;
  }[] = [
    { key: 'risk', label: 'Risk' },
    { key: 'status', label: 'Status' },
    { key: 'evidence', label: 'Evidence' },
    { key: 'incident', label: 'Incident' },
  ];

  return (
    <div
      className={cn('flex flex-wrap gap-1', className)}
      role="group"
      aria-label="Graph overlay toggles"
      data-testid="graph-overlay-toggles"
    >
      {items.map((item) => (
        <Button
          key={item.key}
          variant={toggles[item.key] ? 'default' : 'outline'}
          size="sm"
          data-testid={`graph-overlay-${item.key}`}
          aria-pressed={toggles[item.key]}
          onClick={() => {
            onToggle(item.key);
          }}
        >
          {item.label}
        </Button>
      ))}
    </div>
  );
}

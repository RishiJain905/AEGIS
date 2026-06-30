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
        'w-full rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-base)] px-3 py-1.5 text-sm text-[var(--aegis-text-primary)] placeholder:text-[var(--aegis-text-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--aegis-focus-ring)]',
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
        'rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)] p-3',
        className,
      )}
      data-testid="graph-legend"
      aria-label={title}
    >
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--aegis-text-muted)]">
        {title}
      </p>
      <ul className="flex flex-col gap-1.5">
        {items.map((item) => (
          <li key={item.label} className="flex items-center gap-2 text-xs">
            <span
              className="inline-block h-3 w-3 shrink-0 rounded-full"
              style={{ backgroundColor: item.color }}
              aria-hidden="true"
            />
            <span className="text-[var(--aegis-text-secondary)]">{item.label}</span>
          </li>
        ))}
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
  toggles: { risk: boolean; status: boolean; evidence: boolean; incident: boolean };
  onToggle: (key: 'risk' | 'status' | 'evidence' | 'incident') => void;
  className?: string;
}

export function GraphOverlayToggle({ toggles, onToggle, className }: GraphOverlayToggleProps) {
  const items: { key: 'risk' | 'status' | 'evidence' | 'incident'; label: string }[] = [
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

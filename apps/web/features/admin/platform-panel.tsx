'use client';

import { Badge, ErrorState, LoadingState, MetricTile, Panel } from '@aegis/ui';

import { useAdminSettings } from './use-admin-queries';
import type { AdminSettingsResponse } from './types';

function formatScalar(value: unknown): string {
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number') {
    return String(value);
  }
  if (typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value);
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '—';
  }
  if (Array.isArray(value)) {
    return value.length > 0 ? value.map((item) => formatScalar(item)).join(', ') : '—';
  }
  if (typeof value === 'boolean') {
    return value ? 'enabled' : 'disabled';
  }
  return formatScalar(value);
}

function ConfigSection({ title, values }: { title: string; values: Record<string, unknown> }) {
  const entries = Object.entries(values);
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold text-[var(--aegis-text-primary)]">{title}</h3>
      <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
        {entries.map(([key, value]) => (
          <div
            key={key}
            className="flex items-baseline justify-between gap-3 border-b border-[var(--aegis-border-subtle)] pb-1.5"
          >
            <dt className="text-xs text-[var(--aegis-text-secondary)]">{key}</dt>
            <dd className="font-mono text-xs text-[var(--aegis-text-primary)]">
              {formatValue(value)}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function healthBadge(status: string | undefined) {
  const value = status ?? 'unknown';
  const variant = value === 'ready' || value === 'ok' ? 'default' : 'outline';
  return <Badge variant={variant}>{value}</Badge>;
}

function PlatformContent({ data }: { data: AdminSettingsResponse }) {
  const dependencies = data.health.dependencies ?? [];
  const readyCount = dependencies.filter(
    (dependency) => (dependency.state ?? dependency.status) === 'ready',
  ).length;

  return (
    <div className="space-y-6" data-testid="admin-platform">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricTile label="Environment" value={data.environment} />
        <MetricTile label="Version" value={data.version} />
        <MetricTile
          label="Readiness"
          value={data.health.status ?? 'unknown'}
          trend={
            dependencies.length > 0
              ? `${String(readyCount)}/${String(dependencies.length)} dependencies ready`
              : undefined
          }
        />
        <MetricTile
          label="Provider"
          value={formatScalar(data.provider.defaultProvider ?? 'unknown')}
        />
      </div>

      {dependencies.length > 0 ? (
        <section className="space-y-2">
          <h3 className="text-sm font-semibold text-[var(--aegis-text-primary)]">
            Dependency health
          </h3>
          <ul className="flex flex-wrap gap-2">
            {dependencies.map((dependency) => (
              <li
                key={dependency.name}
                className="flex items-center gap-2 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] px-3 py-2"
              >
                <span className="text-xs font-medium text-[var(--aegis-text-primary)]">
                  {dependency.name}
                </span>
                {healthBadge(dependency.state ?? dependency.status)}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <ConfigSection title="Model provider" values={data.provider} />
      <ConfigSection title="Authentication" values={data.auth} />
      <ConfigSection title="WebSocket" values={data.websocket} />
      <ConfigSection title="Security" values={data.security} />
      <ConfigSection title="Observability" values={data.observability} />

      <p className="text-xs text-[var(--aegis-text-muted)]">
        Secrets (API keys, passwords, client secrets) are never included in this view.
      </p>
    </div>
  );
}

export function PlatformPanel() {
  const query = useAdminSettings(true);

  return (
    <Panel
      title="Platform"
      description="Service health, provider mode, non-secret runtime configuration, and build version."
    >
      {query.isPending ? (
        <LoadingState message="Loading platform settings" />
      ) : query.isError ? (
        <ErrorState
          title="Could not load settings"
          message="Platform settings could not be read. Retry, or confirm the API is reachable."
          onRetry={() => void query.refetch()}
        />
      ) : (
        <PlatformContent data={query.data} />
      )}
    </Panel>
  );
}

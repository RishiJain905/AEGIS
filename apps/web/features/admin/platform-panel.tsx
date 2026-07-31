'use client';

import {
  Badge,
  ErrorState,
  LoadingState,
  MetricTile,
  Panel,
  cn,
  typographyTokens,
} from '@aegis/ui';

import { SectionHeading } from './admin-ui';
import { useAdminSettings } from './use-admin-queries';
import type {
  AdminDependencyStatus,
  AdminModelProviderHealth,
  AdminSettingsResponse,
} from './types';

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
    <section className="space-y-3">
      <SectionHeading count={entries.length}>{title}</SectionHeading>
      <dl className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
        {entries.map(([key, value]) => (
          <div
            key={key}
            className="flex items-baseline justify-between gap-3 border-b border-[var(--aegis-border-subtle)] pb-1.5"
          >
            <dt className={cn(typographyTokens.monoSm, 'uppercase text-[var(--aegis-text-muted)]')}>
              {key}
            </dt>
            <dd
              className={cn(typographyTokens.monoSm, 'text-right text-[var(--aegis-text-primary)]')}
            >
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

/**
 * The API reports dependency health as a DependencyStateV1 (`ok` | `degraded` |
 * `unavailable` | `failed` | `skipped`) — never `ready`, which belongs to the
 * *aggregate* ReadyStatusV1. Counting `ready` here is what produced the
 * "READINESS ready / 0/3 dependencies ready" contradiction (BUG-021); the summary
 * is now derived from the exact records rendered below it.
 */
function dependencyState(dependency: AdminDependencyStatus): string {
  return dependency.state ?? dependency.status ?? 'unknown';
}

function isDependencyHealthy(dependency: AdminDependencyStatus): boolean {
  return dependencyState(dependency) === 'ok';
}

function ProviderDetail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-[var(--aegis-border-subtle)] pb-1.5">
      <dt className={cn(typographyTokens.monoSm, 'uppercase text-[var(--aegis-text-muted)]')}>
        {label}
      </dt>
      <dd className={cn(typographyTokens.monoSm, 'text-right text-[var(--aegis-text-primary)]')}>
        {value}
      </dd>
    </div>
  );
}

/**
 * Model-provider readiness, reported beside — never merged into — infrastructure
 * readiness. AEGIS must stay operable with the model down.
 */
function ModelProviderHealth({ health }: { health: AdminModelProviderHealth }) {
  const servedModel = health.reportedModel ?? health.reportedModels?.[0] ?? null;
  const configuredModel = health.configuredModel ?? null;
  const drifted = health.configuredModelServed === false && configuredModel !== null;

  return (
    <section className="space-y-3" data-testid="admin-model-provider-health">
      <SectionHeading>Model provider health</SectionHeading>
      <div className="space-y-3 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-elevated)_70%,transparent)] px-3 py-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-[var(--aegis-text-primary)]">
            {health.provider}
          </span>
          {healthBadge(health.state)}
        </div>
        <dl className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
          <ProviderDetail label="endpoint" value={formatValue(health.baseUrl)} />
          <ProviderDetail label="served model" value={formatValue(servedModel)} />
          <ProviderDetail label="configured model" value={formatValue(configuredModel)} />
          <ProviderDetail label="last probe" value={formatValue(health.checkedAt)} />
        </dl>
        {drifted ? (
          <p className="text-xs leading-5 text-[var(--aegis-text-muted)]">
            {`Configured model "${String(configuredModel)}" is not served by this endpoint — requests naming it will fail.`}
          </p>
        ) : null}
        {health.message ? (
          <p className="text-xs leading-5 text-[var(--aegis-text-muted)]">{health.message}</p>
        ) : null}
      </div>
    </section>
  );
}

function PlatformContent({ data }: { data: AdminSettingsResponse }) {
  const dependencies = data.health.dependencies ?? [];
  const healthyCount = dependencies.filter(isDependencyHealthy).length;
  const modelProvider = data.health.modelProvider;

  return (
    <div className="space-y-8" data-testid="admin-platform">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricTile label="Environment" value={data.environment} />
        <MetricTile label="Version" value={data.version} />
        <MetricTile
          label="Infrastructure"
          value={data.health.status ?? 'unknown'}
          trend={
            dependencies.length > 0
              ? `${String(healthyCount)}/${String(dependencies.length)} dependencies ok`
              : undefined
          }
        />
        <MetricTile
          label="Provider"
          value={formatScalar(data.provider.defaultProvider ?? 'unknown')}
          trend={modelProvider ? `model probe ${modelProvider.state}` : undefined}
        />
      </div>

      {dependencies.length > 0 ? (
        <section className="space-y-3">
          <SectionHeading count={dependencies.length}>Dependency health</SectionHeading>
          <ul className="flex flex-wrap gap-2">
            {dependencies.map((dependency) => (
              <li
                key={dependency.name}
                className="flex items-center gap-2 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-elevated)_70%,transparent)] px-3 py-2"
              >
                <span className="text-xs font-medium text-[var(--aegis-text-primary)]">
                  {dependency.name}
                </span>
                {healthBadge(dependencyState(dependency))}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {modelProvider ? <ModelProviderHealth health={modelProvider} /> : null}

      <div className="space-y-8">
        <ConfigSection title="Model provider" values={data.provider} />
        <ConfigSection title="Authentication" values={data.auth} />
        <ConfigSection title="WebSocket" values={data.websocket} />
        <ConfigSection title="Security" values={data.security} />
        <ConfigSection title="Observability" values={data.observability} />
      </div>

      <p className="text-xs leading-5 text-[var(--aegis-text-muted)]">
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

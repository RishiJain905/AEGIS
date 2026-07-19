'use client';

import { Panel, cn } from '@aegis/ui';

import type { AgentActivity } from '../lib/incident-model';

const ROLE_BLURB: Record<AgentActivity['role'], string> = {
  WATCHTOWER: 'Alert triage & correlation',
  TRACE: 'Graph expansion & evidence',
  ORACLE: 'Hypothesis reasoning',
  BASTION: 'Response proposals',
  WARDEN: 'Policy validation',
  SCRIBE: 'After-action reporting',
};

export function IncidentAgentRoster({ roster }: { roster: readonly AgentActivity[] }) {
  return (
    <Panel
      title="Agent activity"
      description="Defensive agents that have worked this incident."
      density="compact"
      data-testid="incident-agent-roster"
    >
      <ul className="flex flex-col gap-2" role="list">
        {roster.map((agent) => (
          <li
            key={agent.role}
            className={cn(
              'rounded-[var(--aegis-radius-md)] border p-3',
              agent.present
                ? 'border-[var(--aegis-border-default)] bg-[var(--aegis-surface-raised)]'
                : 'border-[var(--aegis-border-subtle)] bg-transparent opacity-60',
            )}
            data-testid={`agent-role-${agent.role}`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-[family-name:var(--aegis-font-display)] text-sm font-semibold tracking-[0.04em] text-[var(--aegis-text-primary)]">
                {agent.role}
              </span>
              <span
                className={cn(
                  'font-mono text-[0.625rem] uppercase tracking-[0.08em]',
                  agent.present
                    ? 'text-[var(--aegis-status-contained)]'
                    : 'text-[var(--aegis-text-muted)]',
                )}
              >
                {agent.present ? 'Active' : 'Idle'}
              </span>
            </div>
            <p className="mt-0.5 text-[0.625rem] uppercase tracking-[0.08em] text-[var(--aegis-text-muted)]">
              {ROLE_BLURB[agent.role]}
            </p>
            <p className="mt-1 text-xs leading-5 text-[var(--aegis-text-secondary)]">
              {agent.headline}
            </p>
            {agent.present ? (
              <p className="mt-1 font-mono text-[0.625rem] text-[var(--aegis-text-muted)] tabular-nums">
                {agent.metricLabel}: {agent.metricValue}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

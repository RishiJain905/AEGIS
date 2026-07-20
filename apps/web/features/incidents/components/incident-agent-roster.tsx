'use client';

import { Panel, cn, typographyTokens } from '@aegis/ui';

import type { AgentActivity } from '../lib/incident-model';

const ROLE_BLURB: Record<AgentActivity['role'], string> = {
  WATCHTOWER: 'Alert triage & correlation',
  TRACE: 'Graph expansion & evidence',
  ORACLE: 'Hypothesis reasoning',
  BASTION: 'Response proposals',
  WARDEN: 'Policy validation',
  SCRIBE: 'After-action reporting',
};

// Fixed 1–2 char monospace glyph per role, mirroring the RailIdentity "A" glyph
// (accent-soft fill, accent-line border). WATCHTOWER=W / WARDEN=WD avoids a
// duplicate single letter so the roster scans as fast as the nav rail.
const ROLE_GLYPH: Record<AgentActivity['role'], string> = {
  WATCHTOWER: 'W',
  TRACE: 'T',
  ORACLE: 'O',
  BASTION: 'B',
  WARDEN: 'WD',
  SCRIBE: 'S',
};

export function IncidentAgentRoster({ roster }: { roster: readonly AgentActivity[] }) {
  return (
    <Panel
      title="Agent activity"
      description="Defensive agents that have worked this incident."
      density="compact"
      data-testid="incident-agent-roster"
    >
      <ul className="-m-4 divide-y divide-[var(--aegis-border-subtle)]" role="list">
        {roster.map((agent) => (
          <li
            key={agent.role}
            className={cn('px-4 py-3', agent.present ? '' : 'opacity-60')}
            data-testid={`agent-role-${agent.role}`}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2.5">
                <span
                  aria-hidden="true"
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-accent-line)] bg-[var(--aegis-accent-soft)] font-[family-name:var(--aegis-font-mono)] text-[0.6875rem] font-bold tracking-[0.02em] text-[var(--aegis-accent-strong)] shadow-[inset_0_1px_0_rgb(255_255_255_/_0.06)]"
                >
                  {ROLE_GLYPH[agent.role]}
                </span>
                <span className="truncate font-[family-name:var(--aegis-font-display)] text-sm font-semibold tracking-[0.04em] text-[var(--aegis-text-primary)]">
                  {agent.role}
                </span>
              </div>
              <span
                className={cn(
                  typographyTokens.eyebrow,
                  agent.present
                    ? 'text-[var(--aegis-status-contained)]'
                    : 'text-[var(--aegis-text-muted)]',
                )}
              >
                {agent.present ? 'Active' : 'Idle'}
              </span>
            </div>
            <p
              className={cn(
                typographyTokens.eyebrow,
                'mt-1.5 pl-[2.375rem] text-[var(--aegis-text-muted)]',
              )}
            >
              {ROLE_BLURB[agent.role]}
            </p>
            <p className="mt-1 pl-[2.375rem] text-xs leading-5 text-[var(--aegis-text-secondary)]">
              {agent.headline}
            </p>
            {agent.present ? (
              <p
                className={cn(
                  typographyTokens.monoSm,
                  'mt-1 pl-[2.375rem] text-[var(--aegis-text-muted)]',
                )}
              >
                {agent.metricLabel}: {agent.metricValue}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

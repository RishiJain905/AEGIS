'use client';

import type { ReactNode } from 'react';

import { OperationsRail } from '@/features/shell/components/operations-rail';

export interface IncidentWorkspaceProps {
  /** Small eyebrow label above the title, e.g. "Incident triage". */
  eyebrow: string;
  title: string;
  description?: string;
  /** Optional actions rendered on the right of the header (links, buttons). */
  actions?: ReactNode;
  children: ReactNode;
}

/**
 * Dedicated chrome for the incident-centric experience. Unlike
 * `CommandCentreShell` (the live-run graph workspace), this shell deliberately
 * omits the live telemetry graph, live-run transport controls, the live
 * timeline, and the entity inspector. It keeps only the shared operations rail
 * for navigation, so "Incident" reads as a triage/case-management surface
 * rather than a second copy of "Active run".
 */
export function IncidentWorkspace({
  eyebrow,
  title,
  description,
  actions,
  children,
}: IncidentWorkspaceProps) {
  return (
    <div
      className="aegis-command-shell flex min-h-screen flex-col"
      data-testid="incident-workspace"
    >
      <a className="skip-link" href="#incident-content">
        Skip to incident workspace
      </a>
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <OperationsRail />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <header
            className="sticky top-0 z-30 flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-b border-[var(--aegis-border-default)] bg-[color-mix(in_srgb,var(--aegis-surface-rail)_95%,transparent)] px-4 py-4 shadow-[0_8px_24px_rgb(0_0_0_/_0.2)] backdrop-blur-md md:px-6"
            data-testid="incident-workspace-header"
          >
            <div className="min-w-0">
              <p className="font-mono text-[0.625rem] uppercase tracking-[0.16em] text-[var(--aegis-accent-strong)]">
                {eyebrow}
              </p>
              <h1 className="mt-1 truncate font-[family-name:var(--aegis-font-display)] text-lg font-semibold tracking-[0.02em] text-[var(--aegis-text-primary)]">
                {title}
              </h1>
              {description ? (
                <p className="mt-1 max-w-2xl text-sm leading-5 text-[var(--aegis-text-secondary)]">
                  {description}
                </p>
              ) : null}
            </div>
            {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
          </header>
          <main id="incident-content" className="flex min-h-0 flex-1 flex-col gap-5 p-4 md:p-6">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}

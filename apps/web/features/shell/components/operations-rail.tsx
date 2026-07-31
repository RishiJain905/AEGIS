'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState, type ReactNode } from 'react';

import { Button, Drawer, DrawerContent, DrawerHeader, DrawerTitle, Rail } from '@aegis/ui';

import type { ResolvedTheme } from '@/features/shell/contracts/panel-preferences';
import { useActiveRunId } from '@/features/shell/hooks/use-active-run';
import { useTheme } from '@/features/shell/hooks/use-theme';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

// Nav items keyed by their base path. Run-scoped destinations (active run, replay,
// after-action) follow the operator's run — the one named by the route, or the one they
// were last on. With no run at all they render disabled: sending "Active run" to the
// catalogue looked like a broken link, because from the catalogue it went nowhere.
const NAV_ITEMS = [
  { base: '/scenarios', label: 'Scenarios', icon: 'grid', runScoped: false },
  { base: '/runs', label: 'Active run', icon: 'pulse', runScoped: true },
  { base: '/incidents', label: 'Incidents', icon: 'alert', runScoped: false },
  { base: '/replay', label: 'Replay', icon: 'history', runScoped: true },
  { base: '/after-action', label: 'After-action', icon: 'review', runScoped: true },
  { base: '/reports', label: 'Reports', icon: 'report', runScoped: false },
  { base: '/admin', label: 'Admin', icon: 'settings', runScoped: false },
  { base: '/design-system', label: 'Design system', icon: 'design', runScoped: false },
] as const;

type NavIconName = (typeof NAV_ITEMS)[number]['icon'];

// Run-scoped bases that are also a real page on their own. Replay's base renders a run
// picker, so with no run in context the rail can send the operator there to choose one
// instead of going inert — replay was previously reachable only by typing a run's URL.
const SELF_SERVING_RUN_SCOPED_BASES = new Set<string>(['/replay']);

/** A nav item's destination, or `null` when it is run-scoped and there is no run. */
function navHref(item: (typeof NAV_ITEMS)[number], activeRunId: string | null): string | null {
  if (!item.runScoped) {
    return item.base;
  }
  if (activeRunId) {
    return `${item.base}/${activeRunId}`;
  }
  return SELF_SERVING_RUN_SCOPED_BASES.has(item.base) ? item.base : null;
}

const NO_ACTIVE_RUN_HINT = 'No active run — start one from Scenarios';

function NavIcon({ name }: { name: NavIconName }) {
  const paths: Record<NavIconName, ReactNode> = {
    grid: <path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" />,
    pulse: <path d="M3 12h4l2.2-5 4.2 10 2.3-5H21" />,
    alert: <path d="M12 3 2.8 19h18.4L12 3Zm0 5v5m0 3.5v.2" />,
    history: <path d="M4.8 7.5A8 8 0 1 1 4 14m.8-6.5H2m2.8 0V4.7M12 8v4l3 2" />,
    review: <path d="M5 3h11l3 3v15H5V3Zm10 0v4h4M8 12h8m-8 4h6" />,
    report: <path d="M4 20V10m5 10V4m6 16v-7m5 7V7" />,
    settings: (
      <path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Zm0-5v2m0 13v2m8.5-8.5h-2m-13 0h-2m14.5-6-1.4 1.4M7.4 16.6 6 18m12 0-1.4-1.4M7.4 7.4 6 6" />
    ),
    design: <path d="M5 5h14v14H5V5Zm4 0v14m6-14v14M5 10h14m-14 5h14" />,
  };

  return (
    <svg
      aria-hidden="true"
      className="h-[18px] w-[18px] shrink-0"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  );
}

function ChevronIcon({ direction }: { direction: 'left' | 'right' }) {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <path d={direction === 'left' ? 'm12.5 4-6 6 6 6' : 'm7.5 4 6 6-6 6'} />
    </svg>
  );
}

function ThemeIcon({ target }: { target: ResolvedTheme }) {
  return (
    <svg
      aria-hidden="true"
      className="h-[18px] w-[18px] shrink-0"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {target === 'light' ? (
        <>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </>
      ) : (
        <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
      )}
    </svg>
  );
}

function ThemeToggle({ collapsed }: { collapsed: boolean }) {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // `resolvedTheme` is 'dark' on the server / first render and only corrects to
  // the real value in an effect; assume that SSR value until mounted so the icon
  // and accessible name match on hydration (no mismatch warning).
  const effectiveTheme: ResolvedTheme = mounted ? resolvedTheme : 'dark';
  const nextTheme: ResolvedTheme = effectiveTheme === 'dark' ? 'light' : 'dark';
  const actionLabel = `Switch to ${nextTheme} theme`;

  return (
    <Button
      variant="ghost"
      size={collapsed ? 'icon' : 'sm'}
      className={collapsed ? 'w-10 justify-center px-0' : 'w-full justify-start'}
      data-testid="toggle-theme"
      onClick={() => {
        setTheme(nextTheme);
      }}
      aria-label={collapsed ? actionLabel : undefined}
      title={actionLabel}
    >
      <ThemeIcon target={nextTheme} />
      {!collapsed ? <span>{nextTheme === 'light' ? 'Light theme' : 'Dark theme'}</span> : null}
    </Button>
  );
}

function RailIdentity({ collapsed }: { collapsed: boolean }) {
  return (
    <div
      className={
        collapsed
          ? 'mb-2 flex h-11 w-11 items-center justify-center rounded-[var(--aegis-radius-md)] border border-[var(--aegis-accent-line)] bg-[var(--aegis-accent-soft)]'
          : 'mb-2 flex items-center gap-3 border-b border-[var(--aegis-border-subtle)] px-1 pb-4 pt-1'
      }
    >
      <span className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--aegis-radius-md)] border border-[var(--aegis-accent-line)] bg-[var(--aegis-accent-soft)] font-[family-name:var(--aegis-font-display)] text-sm font-bold tracking-[0.08em] text-[var(--aegis-accent-strong)] shadow-[inset_0_1px_0_var(--aegis-border-highlight),0_0_20px_color-mix(in_srgb,var(--aegis-accent-cyan)_22%,transparent)]">
        A
      </span>
      {!collapsed ? (
        <span className="min-w-0">
          <span className="block font-[family-name:var(--aegis-font-display)] text-sm font-semibold tracking-[0.12em] text-[var(--aegis-text-primary)]">
            AEGIS
          </span>
          <span className="block font-mono text-[0.625rem] uppercase tracking-[0.16em] text-[var(--aegis-text-muted)]">
            Command grid
          </span>
        </span>
      ) : null}
    </div>
  );
}

const ACTIVE_PILL =
  'border-[var(--aegis-accent-line)] bg-[var(--aegis-accent-soft)] text-[var(--aegis-accent-strong)] hover:border-[var(--aegis-accent-line)] hover:bg-[var(--aegis-accent-soft)] hover:text-[var(--aegis-accent-strong)]';

function NavLinks({ collapsed }: { collapsed: boolean }) {
  const pathname = usePathname();
  const activeRunId = useActiveRunId();

  return (
    <>
      {NAV_ITEMS.map((item) => {
        const href = navHref(item, activeRunId);
        const active = pathname === item.base || pathname.startsWith(`${item.base}/`);
        const className = collapsed
          ? `relative w-10 justify-center px-0 ${active ? ACTIVE_PILL : ''}`
          : `relative w-full justify-start px-3 ${
              active ? `${ACTIVE_PILL} shadow-[inset_2px_0_0_var(--aegis-accent-cyan)]` : ''
            }`;

        // Unreachable destination: rendered, named and focusable so the rail keeps its
        // shape and the operator can see why, but inert rather than linking somewhere it
        // does not mean.
        if (href === null) {
          return (
            <Button
              key={item.base}
              variant="ghost"
              size="sm"
              disabled
              aria-disabled="true"
              data-testid={`rail-${item.icon}-disabled`}
              className={`${className} cursor-not-allowed opacity-45`}
              title={`${item.label} — ${NO_ACTIVE_RUN_HINT}`}
            >
              <NavIcon name={item.icon} />
              {!collapsed ? <span>{item.label}</span> : null}
            </Button>
          );
        }

        return (
          <Button
            key={item.base}
            asChild
            variant={active ? 'secondary' : 'ghost'}
            size="sm"
            className={className}
          >
            <Link
              href={href}
              aria-current={active ? 'page' : undefined}
              aria-label={collapsed ? item.label : undefined}
              title={collapsed ? item.label : undefined}
            >
              <NavIcon name={item.icon} />
              {!collapsed ? <span>{item.label}</span> : null}
            </Link>
          </Button>
        );
      })}
    </>
  );
}

export function OperationsRail() {
  const collapsed = useWorkspaceUiStore(
    (state) => state.panelPreferences.regions.operationsRail?.collapsed ?? false,
  );
  const togglePanelCollapsed = useWorkspaceUiStore((state) => state.togglePanelCollapsed);
  const mobileRailOpen = useWorkspaceUiStore((state) => state.mobileRailOpen);
  const setMobileRailOpen = useWorkspaceUiStore((state) => state.setMobileRailOpen);

  return (
    <>
      <div className="flex items-center justify-between gap-2 border-b border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-rail)_85%,transparent)] p-3 backdrop-blur-md lg:hidden">
        <RailIdentity collapsed={false} />
        <Button
          variant="outline"
          size="sm"
          data-testid="open-mobile-rail"
          onClick={() => {
            setMobileRailOpen(true);
          }}
        >
          Menu
        </Button>
      </div>

      <Drawer open={mobileRailOpen} onOpenChange={setMobileRailOpen}>
        <DrawerContent>
          <DrawerHeader>
            <DrawerTitle>Operations</DrawerTitle>
          </DrawerHeader>
          <nav aria-label="Mobile operations navigation" className="flex flex-col gap-2 p-4">
            <NavLinks collapsed={false} />
            <ThemeToggle collapsed={false} />
          </nav>
        </DrawerContent>
      </Drawer>

      {/* Vertical margins match the height inset so the rail is centred in the viewport
          whether the page scrolls or the run workspace pins it to a fixed height. */}
      <Rail
        label="Operations navigation"
        collapsed={collapsed}
        responsive={false}
        data-testid="operations-rail"
        className="operations-rail-desktop shrink-0 lg:sticky lg:top-5 lg:my-5 lg:ml-5 lg:h-[calc(100vh-2.5rem)] lg:self-start xl:top-6 xl:my-6 xl:ml-6 xl:h-[calc(100vh-3rem)]"
      >
        <RailIdentity collapsed={collapsed} />
        <ThemeToggle collapsed={collapsed} />
        <Button
          variant="ghost"
          size={collapsed ? 'icon' : 'sm'}
          className={collapsed ? 'w-10 justify-center px-0' : 'w-full justify-start'}
          data-testid="toggle-rail-collapse"
          onClick={() => {
            togglePanelCollapsed('operationsRail');
          }}
          aria-expanded={!collapsed}
          aria-label={collapsed ? 'Expand operations rail' : 'Collapse operations rail'}
        >
          <ChevronIcon direction={collapsed ? 'right' : 'left'} />
          {!collapsed ? <span>Collapse rail</span> : null}
        </Button>
        <NavLinks collapsed={collapsed} />
      </Rail>
    </>
  );
}

'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

import { Button, Drawer, DrawerContent, DrawerHeader, DrawerTitle, Rail } from '@aegis/ui';

import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

const INCIDENT_PATH = `/incidents/${encodeURIComponent('incident:inc_synthetic_001')}`;

const NAV_ITEMS = [
  { href: '/scenarios', label: 'Scenarios', icon: 'grid' },
  {
    href: '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    label: 'Active run',
    icon: 'pulse',
  },
  { href: INCIDENT_PATH, label: 'Incident', icon: 'alert' },
  {
    href: '/replay/run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    label: 'Replay',
    icon: 'history',
  },
  {
    href: '/after-action/run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    label: 'After-action',
    icon: 'review',
  },
  { href: '/reports', label: 'Reports', icon: 'report' },
  { href: '/admin', label: 'Admin', icon: 'settings' },
  { href: '/design-system', label: 'Design system', icon: 'design' },
] as const;

type NavIconName = (typeof NAV_ITEMS)[number]['icon'];

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

function RailIdentity({ collapsed }: { collapsed: boolean }) {
  return (
    <div
      className={
        collapsed
          ? 'mb-2 flex h-11 w-11 items-center justify-center rounded-[var(--aegis-radius-md)] border border-[var(--aegis-accent-line)] bg-[var(--aegis-accent-soft)]'
          : 'mb-2 flex items-center gap-3 border-b border-[var(--aegis-border-subtle)] px-1 pb-4 pt-1'
      }
    >
      <span className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-accent-line)] bg-[var(--aegis-accent-soft)] font-[family-name:var(--aegis-font-display)] text-sm font-bold tracking-[0.08em] text-[var(--aegis-accent-strong)] shadow-[inset_0_1px_0_rgb(255_255_255_/_0.07),0_0_18px_rgb(89_201_234_/_0.1)]">
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

function NavLinks({ collapsed }: { collapsed: boolean }) {
  const pathname = usePathname();

  return (
    <>
      {NAV_ITEMS.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Button
            key={item.href}
            asChild
            variant={active ? 'secondary' : 'ghost'}
            size="sm"
            className={
              collapsed
                ? 'relative w-10 justify-center px-0'
                : `relative w-full justify-start px-3 ${
                    active
                      ? 'border-[var(--aegis-accent-line)] text-[var(--aegis-accent-strong)] before:absolute before:-left-[0.8rem] before:h-5 before:w-0.5 before:rounded-r before:bg-[var(--aegis-accent-cyan)]'
                      : ''
                  }`
            }
          >
            <Link
              href={item.href}
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
      <div className="flex items-center justify-between gap-2 border-b border-[var(--aegis-border-default)] bg-[var(--aegis-surface-rail)] p-3 lg:hidden">
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
          </nav>
        </DrawerContent>
      </Drawer>

      <Rail
        label="Operations navigation"
        collapsed={collapsed}
        responsive={false}
        data-testid="operations-rail"
        className="operations-rail-desktop shrink-0"
      >
        <RailIdentity collapsed={collapsed} />
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

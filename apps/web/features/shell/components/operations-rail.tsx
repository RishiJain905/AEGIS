'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { Button, Drawer, DrawerContent, DrawerHeader, DrawerTitle, Rail } from '@aegis/ui';

import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

const INCIDENT_PATH = `/incidents/${encodeURIComponent('incident:inc_synthetic_001')}`;

const NAV_ITEMS = [
  { href: '/scenarios', label: 'Scenarios' },
  { href: '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV', label: 'Active run' },
  { href: INCIDENT_PATH, label: 'Incident' },
  { href: '/replay/run_01ARZ3NDEKTSV4RRFFQ69G5FAV', label: 'Replay' },
  { href: '/reports', label: 'Reports' },
  { href: '/admin', label: 'Admin' },
  { href: '/design-system', label: 'Design system' },
] as const;

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
            className={collapsed ? 'w-10 justify-center px-0' : 'w-full justify-start'}
          >
            <Link href={item.href} aria-current={active ? 'page' : undefined}>
              {collapsed ? item.label.charAt(0) : item.label}
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
      <div className="flex items-center gap-2 border-b border-[var(--aegis-border-default)] p-3 lg:hidden">
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
        data-testid="operations-rail"
        className="shrink-0"
      >
        <Button
          variant="ghost"
          size="sm"
          className={collapsed ? 'w-10 justify-center px-0' : 'w-full justify-start'}
          data-testid="toggle-rail-collapse"
          onClick={() => {
            togglePanelCollapsed('operationsRail');
          }}
          aria-expanded={!collapsed}
        >
          {collapsed ? '»' : '« Collapse'}
        </Button>
        <NavLinks collapsed={collapsed} />
      </Rail>
    </>
  );
}

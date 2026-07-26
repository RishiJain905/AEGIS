'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useId, useRef, useState } from 'react';

import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@aegis/ui';

import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

interface CommandItem {
  id: string;
  label: string;
  shortcut?: string;
  action: () => void;
}

/**
 * The run the palette's run-scoped commands should target.
 *
 * `activeRunId` in the workspace store is cleared by `resetForRun(null)` the moment the
 * operator leaves a run surface, so it cannot be the only source. The route is read first
 * — the same rule the operations rail uses — so the two navigation surfaces agree on what
 * "the active run" means instead of disagreeing on the same page.
 */
function activeRunIdFromPath(pathname: string | null): string | null {
  if (!pathname) {
    return null;
  }
  const match = /^\/(?:runs|replay|after-action)\/([^/?#]+)/.exec(pathname);
  const captured = match?.[1];
  return captured ? decodeURIComponent(captured) : null;
}

export function CommandPalette() {
  const router = useRouter();
  const pathname = usePathname();
  const listboxId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const lastFocusRef = useRef<HTMLElement | null>(null);

  const open = useWorkspaceUiStore((state) => state.workspace.commandPaletteOpen);
  const setCommandPaletteOpen = useWorkspaceUiStore((state) => state.setCommandPaletteOpen);
  const togglePanelCollapsed = useWorkspaceUiStore((state) => state.togglePanelCollapsed);
  const storedRunId = useWorkspaceUiStore((state) => state.activeRunId);
  const [query, setQuery] = useState('');

  const activeRunId = activeRunIdFromPath(pathname) ?? storedRunId;

  const commands: CommandItem[] = [
    {
      id: 'nav-scenarios',
      label: 'Go to scenarios',
      action: () => {
        router.push('/scenarios');
      },
    },
    // Run-scoped destinations are offered only when there is a run to go to. They
    // previously pointed at a hardcoded fixture run id, which navigated every operator to
    // a run that was not theirs (and, on a fresh install, does not exist).
    ...(activeRunId
      ? [
          {
            id: 'nav-run',
            label: 'Go to active run',
            action: () => {
              router.push(`/runs/${activeRunId}`);
            },
          },
        ]
      : []),
    {
      id: 'nav-incident',
      label: 'Go to incidents',
      action: () => {
        router.push('/incidents');
      },
    },
    ...(activeRunId
      ? [
          {
            id: 'nav-replay',
            label: 'Go to replay',
            action: () => {
              router.push(`/replay/${activeRunId}`);
            },
          },
        ]
      : []),
    {
      id: 'nav-reports',
      label: 'Go to reports',
      action: () => {
        router.push('/reports');
      },
    },
    {
      id: 'nav-admin',
      label: 'Go to admin',
      action: () => {
        router.push('/admin');
      },
    },
    {
      id: 'toggle-rail',
      label: 'Toggle operations rail',
      shortcut: '⌘B',
      action: () => {
        togglePanelCollapsed('operationsRail');
      },
    },
    // The two run-cockpit docks, named as the workspace names them ("Operator console" on
    // the left, "Context channel" on the right) and carrying the shortcuts that actually
    // drive them. The ⌘I entry previously toggled the `inspector` region — a different
    // region, used only by the replay surface — so the advertised shortcut did not match
    // what the command did.
    {
      id: 'toggle-right-dock',
      label: 'Toggle context channel',
      shortcut: '⌘I',
      action: () => {
        togglePanelCollapsed('rightDock');
      },
    },
    {
      id: 'toggle-left-dock',
      label: 'Toggle operator console',
      shortcut: '⌘J',
      action: () => {
        togglePanelCollapsed('leftDock');
      },
    },
    // Replay-only regions. No shortcut is advertised because none is bound to them.
    {
      id: 'toggle-replay-inspector',
      label: 'Toggle replay inspector',
      action: () => {
        togglePanelCollapsed('inspector');
      },
    },
    {
      id: 'toggle-replay-timeline',
      label: 'Toggle replay timeline',
      action: () => {
        togglePanelCollapsed('timeline');
      },
    },
  ];

  const filtered = commands.filter((command) =>
    command.label.toLowerCase().includes(query.trim().toLowerCase()),
  );

  useEffect(() => {
    if (open) {
      lastFocusRef.current = document.activeElement as HTMLElement | null;
      const timer = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => {
        window.clearTimeout(timer);
      };
    }
    if (lastFocusRef.current) {
      lastFocusRef.current.focus();
      lastFocusRef.current = null;
    }
    setQuery('');
    return undefined;
  }, [open]);

  function runCommand(command: CommandItem) {
    command.action();
    setCommandPaletteOpen(false);
  }

  return (
    <Dialog open={open} onOpenChange={setCommandPaletteOpen}>
      <DialogContent data-testid="command-palette" className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Command palette</DialogTitle>
          <DialogDescription>
            Search commands and navigate the command centre. Press ⌘K or Ctrl+K to open.
          </DialogDescription>
        </DialogHeader>
        <input
          ref={inputRef}
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
          }}
          placeholder="Search commands…"
          className="w-full rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-base)] px-3 py-2 text-sm"
          aria-controls={listboxId}
          data-testid="command-palette-input"
        />
        <ul
          id={listboxId}
          role="listbox"
          className="mt-3 max-h-64 overflow-auto"
          data-testid="command-palette-list"
        >
          {filtered.map((command) => (
            <li key={command.id} role="option">
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-between"
                onClick={() => {
                  runCommand(command);
                }}
              >
                <span>{command.label}</span>
                {command.shortcut ? (
                  <span className="text-xs text-[var(--aegis-text-muted)]">{command.shortcut}</span>
                ) : null}
              </Button>
            </li>
          ))}
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-sm text-[var(--aegis-text-secondary)]">
              No matching commands
            </li>
          ) : null}
        </ul>
      </DialogContent>
    </Dialog>
  );
}

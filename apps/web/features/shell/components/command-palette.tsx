'use client';

import { useRouter } from 'next/navigation';
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

export function CommandPalette() {
  const router = useRouter();
  const listboxId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const lastFocusRef = useRef<HTMLElement | null>(null);

  const open = useWorkspaceUiStore((state) => state.workspace.commandPaletteOpen);
  const setCommandPaletteOpen = useWorkspaceUiStore((state) => state.setCommandPaletteOpen);
  const togglePanelCollapsed = useWorkspaceUiStore((state) => state.togglePanelCollapsed);
  const [query, setQuery] = useState('');

  const commands: CommandItem[] = [
    {
      id: 'nav-scenarios',
      label: 'Go to scenarios',
      action: () => {
        router.push('/scenarios');
      },
    },
    {
      id: 'nav-run',
      label: 'Go to active run',
      action: () => {
        router.push('/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV');
      },
    },
    {
      id: 'nav-incident',
      label: 'Go to incident',
      action: () => {
        router.push(`/incidents/${encodeURIComponent('incident:inc_synthetic_001')}`);
      },
    },
    {
      id: 'nav-replay',
      label: 'Go to replay',
      action: () => {
        router.push('/replay/run_01ARZ3NDEKTSV4RRFFQ69G5FAV');
      },
    },
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
    {
      id: 'toggle-inspector',
      label: 'Toggle inspector',
      shortcut: '⌘I',
      action: () => {
        togglePanelCollapsed('inspector');
      },
    },
    {
      id: 'toggle-timeline',
      label: 'Toggle timeline',
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

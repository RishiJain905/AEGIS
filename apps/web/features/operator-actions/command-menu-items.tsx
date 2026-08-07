'use client';

import { Fragment } from 'react';

import { cn, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator } from '@aegis/ui';

import type { ActionClass, CommandMeta } from '@/features/command-surface';

/**
 * Tier headings, in menu order. The menu is built by walking these tiers over whatever
 * command list it was handed, so a per-asset-type catalogue that omits a whole tier simply
 * drops that heading — no geometry depends on the catalogue's length or contents.
 */
const TIERS: readonly { classes: readonly ActionClass[]; label: string }[] = [
  { classes: ['class_0', 'class_1'], label: 'Read & monitor' },
  { classes: ['class_2'], label: 'Containment · needs confirm' },
  { classes: ['class_3'], label: 'Critical · needs confirm' },
];

export interface CommandMenuItemsProps {
  commands: readonly CommandMeta[];
  onSelect: (command: CommandMeta) => void;
  /**
   * True on a terminal run: every item renders disabled so a surface that cannot show a
   * hint (the graph context menu) still never offers a command the server will refuse.
   */
  disabled?: boolean;
}

/** The grouped command list shared by the inspector dropdown and the graph context menu. */
export function CommandMenuItems({ commands, onSelect, disabled = false }: CommandMenuItemsProps) {
  const tiers = TIERS.map((tier) => ({
    label: tier.label,
    commands: commands.filter((command) => tier.classes.includes(command.actionClass)),
  })).filter((tier) => tier.commands.length > 0);

  return (
    <>
      {/* A menu can't show a tooltip, so on a terminal run it says so in its own line
          instead — same vocabulary as the command bar's "Run ended · read-only" badge,
          just compact enough for a dense list (P2, Chrome QA on the rebuilt stack). */}
      {disabled ? (
        <>
          <div
            data-testid="command-menu-run-ended-note"
            className="px-3 py-1.5 text-[0.6875rem] font-medium italic text-[var(--aegis-text-muted)]"
          >
            Run ended — read-only
          </div>
          <DropdownMenuSeparator />
        </>
      ) : null}
      {tiers.map((tier, index) => (
        <Fragment key={tier.label}>
          {index > 0 ? <DropdownMenuSeparator /> : null}
          <DropdownMenuLabel>{tier.label}</DropdownMenuLabel>
          {tier.commands.map((command) => (
            <DropdownMenuItem
              key={command.command}
              disabled={disabled}
              // Belt-and-suspenders over the primitive's own `data-[disabled]` styling: a
              // disabled item must look dead even if that attribute selector doesn't win,
              // and the attribute doubles as a stable, pixel-free test hook.
              data-command-state={disabled ? 'dead' : 'live'}
              className={disabled ? 'opacity-60' : undefined}
              onSelect={() => {
                onSelect(command);
              }}
              data-testid={`action-item-${command.command}`}
            >
              <div className="flex flex-col">
                <span
                  className={cn(
                    !disabled &&
                      command.actionClass === 'class_3' &&
                      'text-[var(--aegis-risk-high)]',
                    disabled && 'text-[var(--aegis-text-muted)]',
                  )}
                >
                  {command.label}
                </span>
                <span
                  className={cn(
                    'text-[10px] text-[var(--aegis-text-muted)]',
                    disabled && 'opacity-70',
                  )}
                >
                  {command.summary}
                </span>
              </div>
            </DropdownMenuItem>
          ))}
        </Fragment>
      ))}
    </>
  );
}

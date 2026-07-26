'use client';

import { Fragment } from 'react';

import { DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator } from '@aegis/ui';

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
}

/** The grouped command list shared by the inspector dropdown and the graph context menu. */
export function CommandMenuItems({ commands, onSelect }: CommandMenuItemsProps) {
  const tiers = TIERS.map((tier) => ({
    label: tier.label,
    commands: commands.filter((command) => tier.classes.includes(command.actionClass)),
  })).filter((tier) => tier.commands.length > 0);

  return (
    <>
      {tiers.map((tier, index) => (
        <Fragment key={tier.label}>
          {index > 0 ? <DropdownMenuSeparator /> : null}
          <DropdownMenuLabel>{tier.label}</DropdownMenuLabel>
          {tier.commands.map((command) => (
            <DropdownMenuItem
              key={command.command}
              onSelect={() => {
                onSelect(command);
              }}
              data-testid={`action-item-${command.command}`}
            >
              <div className="flex flex-col">
                <span
                  className={
                    command.actionClass === 'class_3' ? 'text-[var(--aegis-risk-high)]' : undefined
                  }
                >
                  {command.label}
                </span>
                <span className="text-[10px] text-[var(--aegis-text-muted)]">
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

'use client';

import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu';
import { forwardRef, type ComponentPropsWithoutRef, type HTMLAttributes } from 'react';

import { cn } from '../lib/cn';
import { focusTokens } from '../tokens/tokens';

export const DropdownMenu = DropdownMenuPrimitive.Root;
export const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;
export const DropdownMenuGroup = DropdownMenuPrimitive.Group;
export const DropdownMenuPortal = DropdownMenuPrimitive.Portal;
export const DropdownMenuSub = DropdownMenuPrimitive.Sub;
export const DropdownMenuRadioGroup = DropdownMenuPrimitive.RadioGroup;

export const DropdownMenuSubTrigger = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.SubTrigger> & {
    inset?: boolean;
  }
>(({ className, inset, children, ...props }, ref) => (
  <DropdownMenuPrimitive.SubTrigger
    ref={ref}
    className={cn(
      'flex min-h-10 cursor-pointer select-none items-center rounded-[var(--aegis-radius-sm)] px-3 py-2 text-sm outline-none focus:bg-[var(--aegis-surface-hover)] data-[state=open]:bg-[var(--aegis-surface-hover)] data-[highlighted]:bg-[var(--aegis-surface-hover)]',
      inset && 'pl-8',
      focusTokens.ring,
      className,
    )}
    {...props}
  >
    {children}
  </DropdownMenuPrimitive.SubTrigger>
));
DropdownMenuSubTrigger.displayName = DropdownMenuPrimitive.SubTrigger.displayName;

// Popover surfaces set their background via inline style rather than the
// `bg-[var(--aegis-surface-overlay)]` Tailwind arbitrary-value class: that
// class was observed silently missing from the compiled stylesheet in a
// production build (JIT candidate-scan miss on this exact utility), which
// left the menu fully transparent with inspector content bleeding through.
// Inline style can't be purged, so the opaque surface is guaranteed.
const popoverSurfaceStyle = { backgroundColor: 'var(--aegis-surface-overlay)' } as const;

export const DropdownMenuSubContent = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.SubContent>
>(({ className, style, ...props }, ref) => (
  <DropdownMenuPrimitive.SubContent
    ref={ref}
    style={{ ...popoverSurfaceStyle, ...style }}
    className={cn(
      'z-50 min-w-[10rem] overflow-hidden rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-strong)] p-1.5 shadow-[var(--aegis-shadow-dialog)]',
      className,
    )}
    {...props}
  />
));
DropdownMenuSubContent.displayName = DropdownMenuPrimitive.SubContent.displayName;

export const DropdownMenuContent = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>
>(({ className, style, sideOffset = 4, ...props }, ref) => (
  <DropdownMenuPrimitive.Portal>
    <DropdownMenuPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      style={{ ...popoverSurfaceStyle, ...style }}
      className={cn(
        'z-50 min-w-[10rem] overflow-hidden rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-strong)] p-1.5 shadow-[var(--aegis-shadow-dialog)]',
        className,
      )}
      {...props}
    />
  </DropdownMenuPrimitive.Portal>
));
DropdownMenuContent.displayName = DropdownMenuPrimitive.Content.displayName;

export const DropdownMenuItem = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item> & {
    inset?: boolean;
    destructive?: boolean;
  }
>(({ className, inset, destructive, ...props }, ref) => (
  <DropdownMenuPrimitive.Item
    ref={ref}
    className={cn(
      'relative flex min-h-10 cursor-pointer select-none items-center rounded-[var(--aegis-radius-sm)] px-3 py-2 text-sm outline-none transition-colors focus:bg-[var(--aegis-surface-hover)] focus:text-[var(--aegis-text-primary)] data-[highlighted]:bg-[var(--aegis-surface-hover)] data-[highlighted]:text-[var(--aegis-text-primary)] data-[disabled]:pointer-events-none data-[disabled]:cursor-default data-[disabled]:opacity-50',
      destructive &&
        'text-[var(--aegis-risk-critical)] focus:text-[var(--aegis-risk-critical)] data-[highlighted]:text-[var(--aegis-risk-critical)]',
      inset && 'pl-8',
      focusTokens.ring,
      className,
    )}
    {...props}
  />
));
DropdownMenuItem.displayName = DropdownMenuPrimitive.Item.displayName;

export const DropdownMenuLabel = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Label> & {
    inset?: boolean;
  }
>(({ className, inset, ...props }, ref) => (
  <DropdownMenuPrimitive.Label
    ref={ref}
    className={cn(
      'px-3 py-2 text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-[var(--aegis-text-muted)]',
      inset && 'pl-8',
      className,
    )}
    {...props}
  />
));
DropdownMenuLabel.displayName = DropdownMenuPrimitive.Label.displayName;

export const DropdownMenuSeparator = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Separator>
>(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.Separator
    ref={ref}
    className={cn('-mx-1 my-1 h-px bg-[var(--aegis-border-default)]', className)}
    {...props}
  />
));
DropdownMenuSeparator.displayName = DropdownMenuPrimitive.Separator.displayName;

export const DropdownMenuShortcut = ({ className, ...props }: HTMLAttributes<HTMLSpanElement>) => (
  <span
    className={cn(
      'ml-auto font-mono text-[0.6875rem] tracking-widest text-[var(--aegis-text-muted)]',
      className,
    )}
    {...props}
  />
);

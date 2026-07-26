'use client';

import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import { forwardRef, type ComponentPropsWithoutRef } from 'react';

import { cn } from '../lib/cn';

export const TooltipProvider = TooltipPrimitive.Provider;
export const Tooltip = TooltipPrimitive.Root;
export const TooltipTrigger = TooltipPrimitive.Trigger;

export const TooltipContent = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, style, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      // Inline style, not the bg-[var(--aegis-surface-overlay)] Tailwind
      // class: that exact class was observed missing from the compiled
      // stylesheet in a production build (see dropdown-menu.tsx), leaving
      // the popover transparent. Inline style can't be purged.
      style={{ backgroundColor: 'var(--aegis-surface-overlay)', ...style }}
      className={cn(
        'z-50 max-w-xs overflow-hidden rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-strong)] px-3 py-2 text-xs leading-5 text-[var(--aegis-text-primary)] shadow-[var(--aegis-shadow-dialog)]',
        className,
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

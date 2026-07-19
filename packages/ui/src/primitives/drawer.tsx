'use client';

import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { forwardRef, type ComponentPropsWithoutRef, type HTMLAttributes } from 'react';

import { cn } from '../lib/cn';
import { focusTokens } from '../tokens/tokens';

export const Drawer = DialogPrimitive.Root;
export const DrawerTrigger = DialogPrimitive.Trigger;
export const DrawerClose = DialogPrimitive.Close;
export const DrawerPortal = DialogPrimitive.Portal;

export const DrawerOverlay = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      'fixed inset-0 z-50 bg-[rgb(1_5_9_/_0.78)] backdrop-blur-[3px] aegis-motion-fade',
      className,
    )}
    {...props}
  />
));
DrawerOverlay.displayName = 'DrawerOverlay';

export interface DrawerContentProps
  extends ComponentPropsWithoutRef<typeof DialogPrimitive.Content> {
  side?: 'left' | 'right';
}

export const DrawerContent = forwardRef<HTMLDivElement, DrawerContentProps>(
  ({ className, children, side = 'right', ...props }, ref) => (
    <DrawerPortal>
      <DrawerOverlay />
      <DialogPrimitive.Content
        ref={ref}
        className={cn(
          'fixed z-50 flex h-full w-[min(26rem,92vw)] flex-col border border-[var(--aegis-border-strong)] bg-[linear-gradient(180deg,var(--aegis-surface-raised),var(--aegis-surface-panel))] shadow-[var(--aegis-shadow-dialog)] aegis-motion-slide',
          side === 'right' ? 'right-0 top-0' : 'left-0 top-0',
          focusTokens.ring,
          className,
        )}
        {...props}
      >
        {children}
        <DialogPrimitive.Close
          className={cn(
            'absolute right-3 top-3 flex h-10 w-10 items-center justify-center rounded-[var(--aegis-radius-md)] border border-transparent text-[var(--aegis-text-muted)] hover:border-[var(--aegis-border-default)] hover:bg-[var(--aegis-surface-hover)] hover:text-[var(--aegis-text-primary)]',
            focusTokens.ring,
          )}
          aria-label="Close drawer"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DrawerPortal>
  ),
);
DrawerContent.displayName = 'DrawerContent';

export const DrawerHeader = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      'flex flex-col gap-1.5 border-b border-[var(--aegis-border-subtle)] p-5 pr-14',
      className,
    )}
    {...props}
  />
);

export const DrawerTitle = forwardRef<
  HTMLHeadingElement,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn(
      'font-[family-name:var(--aegis-font-display)] text-lg font-semibold tracking-[0.025em] text-[var(--aegis-text-primary)]',
      className,
    )}
    {...props}
  />
));
DrawerTitle.displayName = 'DrawerTitle';

export const DrawerDescription = forwardRef<
  HTMLParagraphElement,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn('text-sm text-[var(--aegis-text-secondary)]', className)}
    {...props}
  />
));
DrawerDescription.displayName = 'DrawerDescription';

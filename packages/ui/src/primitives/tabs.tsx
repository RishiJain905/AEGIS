'use client';

import * as TabsPrimitive from '@radix-ui/react-tabs';
import { forwardRef, type ComponentPropsWithoutRef } from 'react';

import { cn } from '../lib/cn';
import { focusTokens } from '../tokens/tokens';

export const Tabs = TabsPrimitive.Root;

export const TabsList = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn(
      'inline-flex min-h-11 items-center justify-center rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)] p-1 text-[var(--aegis-text-secondary)] shadow-[var(--aegis-shadow-control)]',
      className,
    )}
    {...props}
  />
));
TabsList.displayName = TabsPrimitive.List.displayName;

export const TabsTrigger = forwardRef<
  HTMLButtonElement,
  ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      'relative inline-flex min-h-9 items-center justify-center whitespace-nowrap rounded-[var(--aegis-radius-sm)] px-3 py-1.5 text-sm font-medium transition-[background-color,color,box-shadow] disabled:pointer-events-none disabled:opacity-50 data-[state=active]:bg-[var(--aegis-surface-raised)] data-[state=active]:text-[var(--aegis-accent-strong)] data-[state=active]:shadow-[var(--aegis-shadow-control)]',
      focusTokens.ring,
      className,
    )}
    {...props}
  />
));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

export const TabsContent = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn('mt-2 focus-visible:outline-none', focusTokens.ring, className)}
    {...props}
  />
));
TabsContent.displayName = TabsPrimitive.Content.displayName;

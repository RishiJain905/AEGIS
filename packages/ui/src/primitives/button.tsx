import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { forwardRef, type ButtonHTMLAttributes } from 'react';

import { cn } from '../lib/cn';
import { focusTokens } from '../tokens/tokens';

const buttonVariants = cva(
  cn(
    'inline-flex min-h-10 items-center justify-center gap-2 whitespace-nowrap font-medium shadow-[var(--aegis-shadow-control)] transition-[background-color,border-color,color,box-shadow] duration-[var(--aegis-motion-duration-fast)] ease-[var(--aegis-motion-ease-standard)] active:shadow-none disabled:pointer-events-none disabled:opacity-50 disabled:shadow-none',
    focusTokens.ring,
  ),
  {
    variants: {
      variant: {
        default:
          'border border-[var(--aegis-accent-strong)]/30 bg-[var(--aegis-accent-cyan)] text-[var(--aegis-text-inverse)] hover:bg-[var(--aegis-accent-strong)] active:border-[var(--aegis-accent-strong)] active:bg-[var(--aegis-accent-strong)]',
        destructive:
          'border border-[var(--aegis-risk-critical)] bg-[var(--aegis-risk-critical-bg)] text-[var(--aegis-risk-critical)] hover:bg-[var(--aegis-risk-critical)] hover:text-[var(--aegis-text-inverse)] active:bg-[var(--aegis-risk-critical)] active:text-[var(--aegis-text-inverse)]',
        outline:
          'border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-elevated)]/70 text-[var(--aegis-text-primary)] hover:border-[var(--aegis-border-strong)] hover:bg-[var(--aegis-surface-hover)] active:border-[var(--aegis-accent-line)] active:bg-[var(--aegis-surface-hover)]',
        ghost:
          'border border-transparent bg-transparent text-[var(--aegis-text-secondary)] shadow-none hover:border-[var(--aegis-border-subtle)] hover:bg-[var(--aegis-surface-hover)] hover:text-[var(--aegis-text-primary)] active:border-[var(--aegis-border-default)] active:bg-[var(--aegis-surface-hover)] active:text-[var(--aegis-text-primary)]',
        secondary:
          'border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-raised)] text-[var(--aegis-text-primary)] hover:border-[var(--aegis-accent-line)] hover:bg-[var(--aegis-surface-hover)] active:border-[var(--aegis-accent-line)] active:bg-[var(--aegis-surface-raised)]',
      },
      size: {
        sm: 'min-h-10 rounded-[var(--aegis-radius-sm)] px-3 text-xs tracking-[0.01em]',
        md: 'h-10 rounded-[var(--aegis-radius-md)] px-4 text-sm',
        lg: 'h-12 rounded-[var(--aegis-radius-md)] px-6 text-base',
        icon: 'h-10 w-10 rounded-[var(--aegis-radius-md)]',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
    },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, type = 'button', ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        type={asChild ? undefined : type}
        {...props}
      />
    );
  },
);
Button.displayName = 'Button';

export { buttonVariants };

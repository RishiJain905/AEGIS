import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { forwardRef, type ButtonHTMLAttributes } from 'react';

import { cn } from '../lib/cn';
import { focusTokens } from '../tokens/tokens';

const buttonVariants = cva(
  cn(
    'inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium transition-colors disabled:pointer-events-none disabled:opacity-50',
    focusTokens.ring,
  ),
  {
    variants: {
      variant: {
        default:
          'bg-[var(--aegis-status-under-investigation)] text-[var(--aegis-text-inverse)] hover:opacity-90',
        destructive: 'bg-[var(--aegis-risk-critical)] text-white hover:opacity-90',
        outline:
          'border border-[var(--aegis-border-default)] bg-transparent text-[var(--aegis-text-primary)] hover:bg-[var(--aegis-surface-elevated)]',
        ghost:
          'bg-transparent text-[var(--aegis-text-primary)] hover:bg-[var(--aegis-surface-elevated)]',
        secondary:
          'bg-[var(--aegis-surface-elevated)] text-[var(--aegis-text-primary)] hover:bg-[var(--aegis-surface-overlay)]',
      },
      size: {
        sm: 'h-8 rounded-[var(--aegis-radius-sm)] px-3 text-sm',
        md: 'h-10 rounded-[var(--aegis-radius-md)] px-4 text-sm',
        lg: 'h-11 rounded-[var(--aegis-radius-md)] px-6 text-base',
        icon: 'h-9 w-9 rounded-[var(--aegis-radius-md)]',
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

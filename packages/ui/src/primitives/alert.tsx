import { cva, type VariantProps } from 'class-variance-authority';
import { forwardRef, type HTMLAttributes } from 'react';

import { cn } from '../lib/cn';

const alertVariants = cva(
  'relative w-full overflow-hidden rounded-[var(--aegis-radius-md)] border border-l-[3px] px-4 py-3.5 text-sm shadow-[var(--aegis-shadow-control)]',
  {
    variants: {
      variant: {
        default:
          'border-[var(--aegis-border-default)] bg-[var(--aegis-surface-elevated)] text-[var(--aegis-text-primary)]',
        info: 'border-[var(--aegis-status-under-investigation)] bg-[var(--aegis-status-under-investigation-bg)]/80 text-[var(--aegis-accent-strong)]',
        warning:
          'border-[var(--aegis-status-suspicious)] bg-[var(--aegis-status-suspicious-bg)] text-[var(--aegis-status-suspicious)]',
        error:
          'border-[var(--aegis-status-error)] bg-[var(--aegis-status-error-bg)] text-[var(--aegis-status-error)]',
        success:
          'border-[var(--aegis-status-normal)] bg-[var(--aegis-status-normal-bg)] text-[var(--aegis-status-normal)]',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
);

export interface AlertProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {
  title?: string;
}

export const Alert = forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant, title, children, role = 'alert', ...props }, ref) => (
    <div ref={ref} role={role} className={cn(alertVariants({ variant }), className)} {...props}>
      {title ? <div className="mb-1 font-semibold tracking-[0.01em]">{title}</div> : null}
      <div className="leading-5 text-[var(--aegis-text-secondary)]">{children}</div>
    </div>
  ),
);
Alert.displayName = 'Alert';

export { alertVariants };

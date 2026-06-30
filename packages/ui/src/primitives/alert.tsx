import { cva, type VariantProps } from 'class-variance-authority';
import { forwardRef, type HTMLAttributes } from 'react';

import { cn } from '../lib/cn';

const alertVariants = cva(
  'relative w-full rounded-[var(--aegis-radius-md)] border px-4 py-3 text-sm',
  {
    variants: {
      variant: {
        default:
          'border-[var(--aegis-border-default)] bg-[var(--aegis-surface-elevated)] text-[var(--aegis-text-primary)]',
        info: 'border-[var(--aegis-status-under-investigation)] bg-[var(--aegis-status-under-investigation-bg)] text-[var(--aegis-status-under-investigation)]',
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
      {title ? <div className="mb-1 font-semibold">{title}</div> : null}
      <div>{children}</div>
    </div>
  ),
);
Alert.displayName = 'Alert';

export { alertVariants };

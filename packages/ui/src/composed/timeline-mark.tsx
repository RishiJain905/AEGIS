import { forwardRef, type HTMLAttributes } from 'react';

import { cn } from '../lib/cn';
import { StatusIcon } from '../semantic/icons';
import { getNodeStatusPresentation } from '../semantic/status';
import type { NodeStatusValue } from '../tokens/status-tokens';

export interface TimelineMarkProps extends HTMLAttributes<HTMLLIElement> {
  timestamp: string;
  label: string;
  description?: string;
  nodeStatus?: NodeStatusValue;
  active?: boolean;
}

export const TimelineMark = forwardRef<HTMLLIElement, TimelineMarkProps>(
  ({ className, timestamp, label, description, nodeStatus, active = false, ...props }, ref) => {
    const presentation = nodeStatus ? getNodeStatusPresentation(nodeStatus) : null;

    return (
      <li
        ref={ref}
        className={cn(
          'group relative flex gap-3 border-l pl-5 pb-7 last:pb-1',
          active
            ? 'border-[var(--aegis-status-under-investigation)]'
            : 'border-[var(--aegis-border-default)]',
          className,
        )}
        {...props}
      >
        <div
          className={cn(
            'absolute -left-[6px] top-1.5 h-[11px] w-[11px] rounded-full border-2 border-[var(--aegis-surface-panel)] shadow-[0_0_0_2px_var(--aegis-border-default)]',
            active
              ? 'bg-[var(--aegis-status-under-investigation)]'
              : 'bg-[var(--aegis-border-strong)]',
          )}
          aria-hidden="true"
        />
        <div className="-mt-0.5 flex min-w-0 flex-col gap-1.5">
          <time
            className="font-mono text-[0.6875rem] tracking-[0.03em] text-[var(--aegis-text-muted)] tabular-nums"
            dateTime={timestamp}
          >
            {timestamp}
          </time>
          <div className="flex items-center gap-2">
            {presentation ? (
              <StatusIcon
                icon={presentation.icon}
                shape={presentation.shape}
                label={presentation.label}
              />
            ) : null}
            <span className="text-sm font-semibold leading-5 text-[var(--aegis-text-primary)]">
              {label}
            </span>
          </div>
          {description ? (
            <p className="max-w-prose text-xs leading-5 text-[var(--aegis-text-secondary)]">
              {description}
            </p>
          ) : null}
        </div>
      </li>
    );
  },
);
TimelineMark.displayName = 'TimelineMark';

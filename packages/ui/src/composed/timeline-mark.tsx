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
          'relative flex gap-3 border-l-2 pl-4 pb-6',
          active
            ? 'border-[var(--aegis-status-under-investigation)]'
            : 'border-[var(--aegis-border-default)]',
          className,
        )}
        {...props}
      >
        <div
          className={cn(
            'absolute -left-[5px] top-1 h-2 w-2 rounded-full',
            active
              ? 'bg-[var(--aegis-status-under-investigation)]'
              : 'bg-[var(--aegis-border-strong)]',
          )}
          aria-hidden="true"
        />
        <div className="flex flex-col gap-1">
          <time className="text-xs text-[var(--aegis-text-muted)]" dateTime={timestamp}>
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
            <span className="text-sm font-medium text-[var(--aegis-text-primary)]">{label}</span>
          </div>
          {description ? (
            <p className="text-xs text-[var(--aegis-text-secondary)]">{description}</p>
          ) : null}
        </div>
      </li>
    );
  },
);
TimelineMark.displayName = 'TimelineMark';

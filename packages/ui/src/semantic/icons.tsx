import {
  AlertTriangle,
  Check,
  Inbox,
  Loader2,
  Search,
  Shield,
  WifiOff,
  XOctagon,
  type LucideIcon,
} from 'lucide-react';

import { cn } from '../lib/cn';
import type { StatusIconName, StatusShape } from './status';

const iconMap: Record<StatusIconName, LucideIcon> = {
  check: Check,
  'alert-triangle': AlertTriangle,
  search: Search,
  shield: Shield,
  'x-octagon': XOctagon,
  loader: Loader2,
  'wifi-off': WifiOff,
  inbox: Inbox,
};

const shapeClasses: Record<StatusShape, string> = {
  circle: 'rounded-full',
  diamond: 'rotate-45 rounded-sm',
  square: 'rounded-sm',
  triangle: 'clip-triangle',
  hexagon: 'rounded-md',
};

export interface StatusIconProps {
  icon: StatusIconName;
  shape: StatusShape;
  className?: string;
  label: string;
  animate?: boolean;
}

export function StatusIcon({ icon, shape, className, label, animate = false }: StatusIconProps) {
  const Icon = iconMap[icon];
  const isLoader = icon === 'loader';

  return (
    <span
      className={cn(
        'inline-flex h-5 w-5 items-center justify-center',
        shapeClasses[shape],
        className,
      )}
      role="img"
      aria-label={label}
    >
      <Icon
        className={cn('h-3.5 w-3.5', isLoader && animate && 'animate-spin')}
        aria-hidden="true"
      />
    </span>
  );
}

export interface RiskIconProps {
  band: 'low' | 'medium' | 'high' | 'critical';
  className?: string;
}

const riskShapes: Record<RiskIconProps['band'], StatusShape> = {
  low: 'circle',
  medium: 'triangle',
  high: 'diamond',
  critical: 'square',
};

export function RiskIcon({ band, className }: RiskIconProps) {
  const icon: StatusIconName =
    band === 'low'
      ? 'check'
      : band === 'medium'
        ? 'alert-triangle'
        : band === 'high'
          ? 'search'
          : 'x-octagon';

  return (
    <StatusIcon
      icon={icon}
      shape={riskShapes[band]}
      className={className}
      label={`Risk level: ${band}`}
    />
  );
}

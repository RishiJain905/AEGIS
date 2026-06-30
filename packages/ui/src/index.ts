import { WORKSPACE_VERSION } from '@aegis/contracts-ts';

export function formatPlatformStatus(service: string): string {
  return `${service}@${WORKSPACE_VERSION}`;
}

export { WORKSPACE_VERSION };

// Tokens
export * from './tokens/tokens';
export * from './tokens/status-tokens';
export * from './tokens/motion-tokens';

// Utilities
export { cn } from './lib/cn';

// Motion
export { useReducedMotion, getReducedMotionPreference } from './motion/use-reduced-motion';

// Semantic
export * from './semantic/status';
export * from './semantic/risk';
export { StatusIcon, RiskIcon } from './semantic/icons';
export type { StatusIconProps, RiskIconProps } from './semantic/icons';

// Primitives
export { Button, buttonVariants } from './primitives/button';
export type { ButtonProps } from './primitives/button';
export { Badge, badgeVariants } from './primitives/badge';
export type { BadgeProps } from './primitives/badge';
export { Alert, alertVariants } from './primitives/alert';
export type { AlertProps } from './primitives/alert';
export { Skeleton } from './primitives/skeleton';
export type { SkeletonProps } from './primitives/skeleton';
export { Separator } from './primitives/separator';
export { VisuallyHidden } from './primitives/visually-hidden';
export {
  Dialog,
  DialogTrigger,
  DialogClose,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './primitives/dialog';
export {
  Drawer,
  DrawerTrigger,
  DrawerClose,
  DrawerPortal,
  DrawerOverlay,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
} from './primitives/drawer';
export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuGroup,
  DropdownMenuPortal,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuRadioGroup,
} from './primitives/dropdown-menu';
export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from './primitives/tooltip';
export { Tabs, TabsList, TabsTrigger, TabsContent } from './primitives/tabs';

// Composed
export { Panel } from './composed/panel';
export type { PanelProps, DensityToken } from './composed/panel';
export { Rail } from './composed/rail';
export type { RailProps } from './composed/rail';
export { Card } from './composed/card';
export type { CardProps } from './composed/card';
export { DataTable, DataTableContainer } from './composed/data-table';
export type { DataTableColumn, DataTableProps } from './composed/data-table';
export { MetricTile } from './composed/metric-tile';
export type { MetricTileProps } from './composed/metric-tile';
export { TimelineMark } from './composed/timeline-mark';
export type { TimelineMarkProps } from './composed/timeline-mark';
export { LoadingState, EmptyState, ErrorState, DisconnectedState } from './composed/state-shells';
export type {
  LoadingStateProps,
  EmptyStateProps,
  ErrorStateProps,
  DisconnectedStateProps,
} from './composed/state-shells';

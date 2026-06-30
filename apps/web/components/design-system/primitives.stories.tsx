import type { Meta, StoryObj } from '@storybook/react';
import { NodeStatus } from '@aegis/contracts-ts';
import {
  Alert,
  Badge,
  Button,
  Card,
  DisconnectedState,
  EmptyState,
  ErrorState,
  LoadingState,
  MetricTile,
  Panel,
  Skeleton,
} from '@aegis/ui';

const meta: Meta = {
  title: 'Design System/Primitives',
  parameters: { layout: 'padded' },
};

export default meta;

export const Buttons: StoryObj = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      <Button>Default</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="outline">Outline</Button>
      <Button variant="ghost">Ghost</Button>
      <Button variant="destructive">Destructive</Button>
      <Button disabled>Disabled</Button>
    </div>
  ),
};

export const StatusBadges: StoryObj = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      <Badge nodeStatus={NodeStatus.NORMAL} />
      <Badge nodeStatus={NodeStatus.SUSPICIOUS} />
      <Badge nodeStatus={NodeStatus.UNDER_INVESTIGATION} />
      <Badge nodeStatus={NodeStatus.CONTAINED} />
      <Badge nodeStatus={NodeStatus.COMPROMISED} />
      <Badge operationalStatus="loading" />
      <Badge operationalStatus="error" />
      <Badge operationalStatus="disconnected" />
      <Badge operationalStatus="empty" />
    </div>
  ),
};

export const Alerts: StoryObj = {
  render: () => (
    <div className="flex max-w-lg flex-col gap-3">
      <Alert variant="default" title="Default">
        Neutral operational notice.
      </Alert>
      <Alert variant="info" title="Info">
        Investigation update available.
      </Alert>
      <Alert variant="warning" title="Warning">
        Elevated watch on segment B.
      </Alert>
      <Alert variant="error" title="Error">
        Failed to load incident timeline.
      </Alert>
      <Alert variant="success" title="Success">
        Containment confirmed in simulation.
      </Alert>
    </div>
  ),
};

export const MetricTiles: StoryObj = {
  render: () => (
    <div className="grid max-w-3xl grid-cols-1 gap-4 md:grid-cols-3">
      <MetricTile label="Alerts" value={8} riskBand="medium" />
      <MetricTile label="Assets" value={142} nodeStatus={NodeStatus.NORMAL} />
      <MetricTile label="Incidents" value={3} riskBand="critical" trend="+1 today" />
    </div>
  ),
};

export const StateShells: StoryObj = {
  render: () => (
    <div className="grid max-w-3xl grid-cols-1 gap-4 md:grid-cols-2">
      <Panel title="Loading">
        <LoadingState />
      </Panel>
      <Panel title="Empty">
        <EmptyState />
      </Panel>
      <Panel title="Error">
        <ErrorState />
      </Panel>
      <Panel title="Disconnected">
        <DisconnectedState />
      </Panel>
    </div>
  ),
};

export const CardAndSkeleton: StoryObj = {
  render: () => (
    <Card
      title="Loading card"
      description="Skeleton placeholder content"
      footer={<Skeleton className="h-4 w-24" />}
    >
      <Skeleton className="mb-2 h-4 w-full" />
      <Skeleton className="h-4 w-3/4" />
    </Card>
  ),
};

import type { Meta, StoryObj } from '@storybook/react';
import { NodeStatus } from '@aegis/contracts-ts';
import {
  Button,
  DataTable,
  DataTableContainer,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  Panel,
  Rail,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  TimelineMark,
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@aegis/ui';

const meta: Meta = {
  title: 'Design System/Composed',
  parameters: { layout: 'fullscreen' },
};

export default meta;

export const PanelAndRail: StoryObj = {
  render: () => (
    <div className="flex min-h-[20rem]">
      <Rail>
        <Button variant="ghost" size="sm">
          Ops
        </Button>
        <Button variant="ghost" size="sm">
          Graph
        </Button>
      </Rail>
      <Panel title="Main panel" description="Comfortable density by default" className="m-4 flex-1">
        <p className="text-sm text-text-secondary">
          Panel content area for Phase 04 shell integration.
        </p>
      </Panel>
    </div>
  ),
};

export const DataTableStory: StoryObj = {
  render: () => (
    <DataTableContainer className="max-w-2xl p-4">
      <DataTable
        caption="Asset overview"
        columns={[
          { key: 'asset', header: 'Asset' },
          { key: 'status', header: 'Status' },
          { key: 'risk', header: 'Risk' },
        ]}
        data={[
          { asset: 'asset:svc-api', status: 'suspicious', risk: 'High' },
          { asset: 'asset:svc-db', status: 'normal', risk: 'Low' },
        ]}
      />
    </DataTableContainer>
  ),
};

export const Timeline: StoryObj = {
  render: () => (
    <ol className="max-w-md list-none p-4">
      <TimelineMark
        timestamp="2026-06-30T09:00:00Z"
        label="Alert raised"
        nodeStatus={NodeStatus.SUSPICIOUS}
      />
      <TimelineMark
        timestamp="2026-06-30T09:30:00Z"
        label="Investigation started"
        nodeStatus={NodeStatus.UNDER_INVESTIGATION}
        active
      />
    </ol>
  ),
};

export const DialogAndTabs: StoryObj = {
  render: () => (
    <TooltipProvider>
      <div className="flex flex-col gap-4 p-6">
        <Tabs defaultValue="a">
          <TabsList>
            <TabsTrigger value="a">Live</TabsTrigger>
            <TabsTrigger value="b">Replay</TabsTrigger>
          </TabsList>
          <TabsContent value="a">Live mode content</TabsContent>
          <TabsContent value="b">Replay mode content</TabsContent>
        </Tabs>
        <Dialog>
          <DialogTrigger asChild>
            <Button>Open dialog</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Dialog title</DialogTitle>
              <DialogDescription>Accessible modal with focus trap.</DialogDescription>
            </DialogHeader>
          </DialogContent>
        </Dialog>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="outline">Tooltip trigger</Button>
          </TooltipTrigger>
          <TooltipContent>Supplementary detail</TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  ),
};

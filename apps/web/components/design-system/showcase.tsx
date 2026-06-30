'use client';

import { NodeStatus } from '@aegis/contracts-ts';
import type { NodeStatusValue } from '@aegis/ui';
import {
  Alert,
  Badge,
  Button,
  Card,
  DataTable,
  DataTableContainer,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DisconnectedState,
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  EmptyState,
  ErrorState,
  LoadingState,
  MetricTile,
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

const tableData = [
  { asset: 'asset:svc-api-gateway', status: 'suspicious', risk: 'High' },
  { asset: 'asset:svc-logistics-api', status: 'normal', risk: 'Low' },
  { asset: 'asset:db-customer-records', status: 'under_investigation', risk: 'Medium' },
];

export function DesignSystemShowcase() {
  return (
    <TooltipProvider>
      <div className="flex min-h-screen flex-col lg:flex-row">
        <Rail label="Design system navigation">
          <Button variant="ghost" size="sm" className="w-full justify-start">
            Tokens
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start">
            Components
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start">
            States
          </Button>
        </Rail>

        <div className="flex flex-1 flex-col gap-6 p-6">
          <header>
            <h1 className="text-2xl font-semibold">Command-Centre Design System</h1>
            <p className="text-sm text-text-secondary">
              Accessible primitives, semantic status styling, and composition patterns for AEGIS.
            </p>
          </header>

          <DisconnectedState data-testid="disconnected-state" />

          <section
            aria-labelledby="status-heading"
            className="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
          >
            <h2 id="status-heading" className="sr-only">
              Status badges
            </h2>
            <Badge nodeStatus={NodeStatus.NORMAL} />
            <Badge nodeStatus={NodeStatus.SUSPICIOUS} />
            <Badge nodeStatus={NodeStatus.UNDER_INVESTIGATION} />
            <Badge nodeStatus={NodeStatus.CONTAINED} />
            <Badge nodeStatus={NodeStatus.COMPROMISED} />
          </section>

          <section className="grid gap-4 md:grid-cols-3">
            <MetricTile
              label="Active alerts"
              value={12}
              riskBand="high"
              trend="+3 since last hour"
            />
            <MetricTile label="Contained assets" value={4} nodeStatus={NodeStatus.CONTAINED} />
            <MetricTile label="Open incidents" value={2} riskBand="critical" />
          </section>

          <Panel
            title="Operational table"
            description="Keyboard-focusable rows with semantic status"
          >
            <DataTableContainer className="mt-4 p-2">
              <DataTable
                caption="Asset status overview"
                columns={[
                  { key: 'asset', header: 'Asset' },
                  {
                    key: 'status',
                    header: 'Status',
                    render: (row) => (
                      <Badge nodeStatus={row.status as NodeStatusValue}>{row.status}</Badge>
                    ),
                  },
                  { key: 'risk', header: 'Risk' },
                ]}
                data={tableData}
              />
            </DataTableContainer>
          </Panel>

          <Card title="Alerts" description="Semantic variants with text and icon meaning">
            <div className="flex flex-col gap-3">
              <Alert variant="info" title="Investigation in progress">
                TRACE agent is correlating authentication anomalies.
              </Alert>
              <Alert variant="warning" title="Elevated watch">
                Unusual east-west traffic detected on segment B.
              </Alert>
            </div>
          </Card>

          <Tabs defaultValue="timeline">
            <TabsList aria-label="Showcase sections">
              <TabsTrigger value="timeline">Timeline</TabsTrigger>
              <TabsTrigger value="overlays">Overlays</TabsTrigger>
              <TabsTrigger value="states">States</TabsTrigger>
            </TabsList>
            <TabsContent value="timeline">
              <ol className="mt-4 list-none pl-0">
                <TimelineMark
                  timestamp="2026-06-30T10:00:00Z"
                  label="Initial alert"
                  description="Suspicious authentication burst"
                  nodeStatus={NodeStatus.SUSPICIOUS}
                />
                <TimelineMark
                  timestamp="2026-06-30T10:15:00Z"
                  label="Investigation opened"
                  nodeStatus={NodeStatus.UNDER_INVESTIGATION}
                  active
                />
              </ol>
            </TabsContent>
            <TabsContent value="overlays">
              <div className="mt-4 flex flex-wrap gap-3">
                <Dialog>
                  <DialogTrigger asChild>
                    <Button data-testid="open-dialog">Open dialog</Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Confirm containment</DialogTitle>
                      <DialogDescription>
                        This action isolates the selected asset in the simulation. Review before
                        approving.
                      </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                      <Button variant="outline">Cancel</Button>
                      <Button variant="destructive">Contain asset</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>

                <Drawer>
                  <DrawerTrigger asChild>
                    <Button variant="secondary">Open drawer</Button>
                  </DrawerTrigger>
                  <DrawerContent>
                    <DrawerHeader>
                      <DrawerTitle>Inspector panel</DrawerTitle>
                      <DrawerDescription>
                        Evidence and hypothesis details appear here.
                      </DrawerDescription>
                    </DrawerHeader>
                  </DrawerContent>
                </Drawer>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" data-testid="open-menu">
                      Open menu
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    <DropdownMenuLabel>Actions</DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem>View evidence</DropdownMenuItem>
                    <DropdownMenuItem destructive>Escalate incident</DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>

                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="ghost">Hover for tooltip</Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    Supplementary context only — not essential information.
                  </TooltipContent>
                </Tooltip>
              </div>
            </TabsContent>
            <TabsContent value="states">
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <LoadingState />
                <EmptyState />
                <ErrorState onRetry={() => undefined} />
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </TooltipProvider>
  );
}

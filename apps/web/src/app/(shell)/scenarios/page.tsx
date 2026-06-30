'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';

import {
  Button,
  DataTable,
  DataTableContainer,
  EmptyState,
  ErrorState,
  LoadingState,
  Panel,
} from '@aegis/ui';

import { CommandCentreShell } from '@/features/shell/components/command-centre-shell';
import { useScenarios } from '@/features/shell/hooks/use-shell-queries';

export default function ScenariosPage() {
  const router = useRouter();
  const scenariosQuery = useScenarios();

  return (
    <CommandCentreShell>
      <Panel title="Scenario selection" description="Choose a scenario to start or resume a run">
        {scenariosQuery.isPending ? <LoadingState message="Loading scenarios…" /> : null}
        {scenariosQuery.isError ? (
          <ErrorState
            data-testid="scenarios-error"
            message="Unable to load scenarios."
            onRetry={() => void scenariosQuery.refetch()}
          />
        ) : null}
        {scenariosQuery.isSuccess && scenariosQuery.data.length === 0 ? (
          <EmptyState
            data-testid="scenarios-empty"
            title="No scenarios available"
            description="Published scenarios will appear here when the simulation platform is connected."
          />
        ) : null}
        {scenariosQuery.isSuccess && scenariosQuery.data.length > 0 ? (
          <DataTableContainer className="mt-4">
            <DataTable
              caption="Available scenarios"
              data-testid="scenarios-table"
              columns={[
                { key: 'name', header: 'Name' },
                { key: 'id', header: 'ID' },
                {
                  key: 'actions',
                  header: 'Actions',
                  render: () => (
                    <Button
                      size="sm"
                      onClick={() => {
                        router.push('/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV');
                      }}
                    >
                      Open run
                    </Button>
                  ),
                },
              ]}
              data={scenariosQuery.data.map((scenario: { name: string; id: string }) => ({
                name: scenario.name,
                id: scenario.id,
                actions: scenario.id,
              }))}
            />
          </DataTableContainer>
        ) : null}
        <div className="mt-4">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/design-system">Design system showcase</Link>
          </Button>
        </div>
      </Panel>
    </CommandCentreShell>
  );
}

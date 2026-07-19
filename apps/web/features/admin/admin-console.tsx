'use client';

import {
  EmptyState,
  LoadingState,
  Panel,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@aegis/ui';

import { useAuth } from '@/features/auth';

import { PlatformPanel } from './platform-panel';
import { PolicyPanel } from './policy-panel';
import { UsersPanel } from './users-panel';

const ADMIN_MANAGE = 'admin:manage';

export function AdminConsole() {
  const { isLoading, isAuthenticated, hasPermission } = useAuth();

  if (isLoading) {
    return (
      <Panel title="Administration" description="Platform administration">
        <LoadingState message="Checking administrator access" />
      </Panel>
    );
  }

  // Client-side gate is a courtesy only; every /api/v1/admin/* endpoint independently
  // enforces admin:manage server-side, so a non-admin who bypasses this still gets 403.
  if (!isAuthenticated || !hasPermission(ADMIN_MANAGE)) {
    return (
      <Panel title="Administration" description="Platform administration">
        <EmptyState
          title="Administrator access required"
          description="These tools require the admin:manage permission. Sign in with an administrator identity to manage users, review enforced policy, and inspect platform settings."
        />
      </Panel>
    );
  }

  return (
    <Tabs defaultValue="users" className="flex flex-col gap-4">
      <TabsList aria-label="Administration sections">
        <TabsTrigger value="users">Users &amp; Roles</TabsTrigger>
        <TabsTrigger value="policy">Policy</TabsTrigger>
        <TabsTrigger value="platform">Platform</TabsTrigger>
      </TabsList>
      <TabsContent value="users">
        <UsersPanel />
      </TabsContent>
      <TabsContent value="policy">
        <PolicyPanel />
      </TabsContent>
      <TabsContent value="platform">
        <PlatformPanel />
      </TabsContent>
    </Tabs>
  );
}

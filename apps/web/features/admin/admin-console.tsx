'use client';

import type { ReactNode } from 'react';

import {
  EmptyState,
  LoadingState,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  cn,
  typographyTokens,
} from '@aegis/ui';

import { useAuth } from '@/features/auth';

import { PlatformPanel } from './platform-panel';
import { PolicyPanel } from './policy-panel';
import { UsersPanel } from './users-panel';

const ADMIN_MANAGE = 'admin:manage';

function AdminHeader() {
  return (
    <header className="flex max-w-2xl flex-col gap-3">
      <span className="inline-flex items-center gap-2">
        <span
          aria-hidden="true"
          className="size-1.5 rounded-full bg-[var(--aegis-accent-cyan)] shadow-[0_0_10px_var(--aegis-accent-cyan)]"
        />
        <span className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-muted)]')}>
          AEGIS Command · Platform
        </span>
      </span>
      <h1 className="font-[family-name:var(--aegis-font-display)] text-[2rem] font-semibold leading-[1.1] tracking-[-0.01em] text-[var(--aegis-text-primary)] sm:text-[2.25rem]">
        Administration console
      </h1>
      <p className="text-[0.9375rem] leading-6 text-[var(--aegis-text-secondary)]">
        Manage authorized identities, review the server-enforced policy matrix, and inspect platform
        health and non-secret runtime configuration.
      </p>
    </header>
  );
}

function AdminNotice({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-[var(--aegis-radius-xl)] border border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_82%,transparent)] p-6 shadow-[var(--aegis-shadow-panel)] backdrop-blur-xl">
      {children}
    </div>
  );
}

export function AdminConsole() {
  const { isLoading, isAuthenticated, hasPermission } = useAuth();

  if (isLoading) {
    return (
      <section className="flex flex-col gap-8">
        <AdminHeader />
        <AdminNotice>
          <LoadingState message="Checking administrator access" />
        </AdminNotice>
      </section>
    );
  }

  // Client-side gate is a courtesy only; every /api/v1/admin/* endpoint independently
  // enforces admin:manage server-side, so a non-admin who bypasses this still gets 403.
  if (!isAuthenticated || !hasPermission(ADMIN_MANAGE)) {
    return (
      <section className="flex flex-col gap-8">
        <AdminHeader />
        <AdminNotice>
          <EmptyState
            title="Administrator access required"
            description="These tools require the admin:manage permission. Sign in with an administrator identity to manage users, review enforced policy, and inspect platform settings."
          />
        </AdminNotice>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-8">
      <AdminHeader />
      <Tabs defaultValue="users" className="flex flex-col gap-5">
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
    </section>
  );
}

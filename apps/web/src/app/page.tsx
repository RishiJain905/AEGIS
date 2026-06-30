import Link from 'next/link';

import { formatPlatformStatus } from '@aegis/ui';

export default function HomePage() {
  const status = formatPlatformStatus('web');

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 p-8">
      <h1 className="text-3xl font-semibold">AEGIS Command</h1>
      <p className="text-text-secondary">Platform status: {status}</p>
      <p className="text-text-secondary">Phase 03 — Command-Centre Design System.</p>
      <Link
        href="/design-system"
        className="inline-flex w-fit items-center rounded-md border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-elevated)] px-4 py-2 text-sm font-medium text-[var(--aegis-text-primary)] hover:bg-[var(--aegis-surface-overlay)]"
      >
        View design system showcase
      </Link>
    </main>
  );
}

import Link from 'next/link';

import { Button } from '@aegis/ui';

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col items-start justify-center gap-4 p-8">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="text-sm text-[var(--aegis-text-secondary)]">
        The requested workspace route does not exist or the entity ID is invalid.
      </p>
      <Button asChild>
        <Link href="/scenarios">Return to scenarios</Link>
      </Button>
    </main>
  );
}

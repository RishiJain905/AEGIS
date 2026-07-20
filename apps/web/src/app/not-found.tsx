import Link from 'next/link';

import { Button, cn, typographyTokens } from '@aegis/ui';

export default function NotFound() {
  return (
    <main className="aegis-command-shell relative flex min-h-screen flex-col items-center justify-center px-6 py-16">
      <div className="flex w-full max-w-md flex-col items-center gap-6 text-center">
        <span className="inline-flex items-center gap-2">
          <span
            aria-hidden="true"
            className="size-1.5 rounded-full bg-[var(--aegis-accent-cyan)] shadow-[0_0_10px_var(--aegis-accent-cyan)]"
          />
          <span className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-muted)]')}>
            Error 404 · Route not found
          </span>
        </span>
        <div className="flex flex-col items-center gap-3">
          <h1 className="font-[family-name:var(--aegis-font-display)] text-[2.5rem] font-semibold leading-[1.05] tracking-[-0.01em] text-[var(--aegis-text-primary)]">
            Page not found
          </h1>
          <p className="text-[0.9375rem] leading-6 text-[var(--aegis-text-secondary)]">
            The requested workspace route does not exist, or the entity ID is invalid. It may have
            been retired, or the run has ended.
          </p>
        </div>
        <Button asChild>
          <Link href="/scenarios">Return to operations</Link>
        </Button>
      </div>
    </main>
  );
}

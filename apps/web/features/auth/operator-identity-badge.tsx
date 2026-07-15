'use client';

import { NodeStatus } from '@aegis/contracts-ts';
import { Badge, Button } from '@aegis/ui';
import { useRouter } from 'next/navigation';

import { useAuth } from '@/features/auth/auth-provider';

export function OperatorIdentityBadge() {
  const auth = useAuth();
  const router = useRouter();

  if (auth.isLoading) {
    return (
      <span className="text-xs text-[var(--aegis-text-secondary)]" data-testid="auth-loading">
        Checking session…
      </span>
    );
  }

  if (!auth.actor) {
    return (
      <Button
        data-testid="sign-in-link"
        onClick={() => {
          router.push('/sign-in');
        }}
      >
        Sign in
      </Button>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="operator-identity">
      <Badge nodeStatus={NodeStatus.NORMAL} data-testid="operator-display-name">
        {auth.actor.displayName}
      </Badge>
      <span className="font-mono text-xs text-[var(--aegis-text-secondary)]" data-testid="operator-roles">
        {auth.actor.roles.join(', ')}
      </span>
      <Button
        data-testid="logout-button"
        onClick={() => {
          void auth.logout().then(() => {
            router.push('/sign-in');
          });
        }}
      >
        Log out
      </Button>
    </div>
  );
}

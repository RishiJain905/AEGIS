'use client';

import { CommandCentreShell } from '@/features/shell/components';
import { AdminConsole } from '@/features/admin';

export default function AdminPage() {
  return (
    <CommandCentreShell>
      <AdminConsole />
    </CommandCentreShell>
  );
}

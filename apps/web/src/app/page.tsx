import type { Metadata } from 'next';
import { formatPlatformStatus } from '@aegis/ui';

export const metadata: Metadata = {
  title: 'AEGIS Command',
  description: 'Interactive cyber-defence simulation and defensive-agent evaluation platform',
};

export default function HomePage() {
  const status = formatPlatformStatus('web');

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', padding: '2rem' }}>
      <h1>AEGIS Command</h1>
      <p>Platform status: {status}</p>
      <p>Phase 00 — repository and engineering standards baseline.</p>
    </main>
  );
}

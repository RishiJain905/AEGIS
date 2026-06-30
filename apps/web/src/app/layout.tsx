import type { Metadata } from 'next';

import './globals.css';

export const metadata: Metadata = {
  title: 'AEGIS Command',
  description: 'Interactive cyber-defence simulation and defensive-agent evaluation platform',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-surface-base font-sans text-text-primary antialiased">{children}</body>
    </html>
  );
}

import type { Metadata } from 'next';

import { ThemeScript } from '@/features/shell/components/theme-script';
import { Providers } from '@/lib/providers';

import './globals.css';

export const metadata: Metadata = {
  title: 'AEGIS Command',
  description: 'Interactive cyber-defence simulation and defensive-agent evaluation platform',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-surface-base font-sans text-text-primary antialiased">
        <ThemeScript />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

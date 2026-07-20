import type { Metadata } from 'next';
import { Archivo, Chakra_Petch, JetBrains_Mono } from 'next/font/google';

import { ThemeScript } from '@/features/shell/components/theme-script';
import { Providers } from '@/lib/providers';

import './globals.css';

const archivo = Archivo({
  subsets: ['latin'],
  variable: '--font-archivo',
  display: 'swap',
});

const chakra = Chakra_Petch({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-chakra',
  display: 'swap',
});

const jetbrains = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'AEGIS Command',
  description: 'Interactive cyber-defence simulation and defensive-agent evaluation platform',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${archivo.variable} ${chakra.variable} ${jetbrains.variable}`}
    >
      <body className="bg-surface-base font-sans text-text-primary antialiased">
        <ThemeScript />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

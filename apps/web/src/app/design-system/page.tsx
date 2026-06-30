import type { Metadata } from 'next';

import { DesignSystemShowcase } from '@/components/design-system';

export const metadata: Metadata = {
  title: 'Design System — AEGIS Command',
  description: 'Command-centre design system showcase and component catalogue',
};

export default function DesignSystemPage() {
  return <DesignSystemShowcase />;
}

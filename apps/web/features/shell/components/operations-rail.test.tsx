import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { setTheme, useTheme } = vi.hoisted(() => {
  const setThemeFn = vi.fn();
  return {
    setTheme: setThemeFn,
    useTheme: vi.fn(() => ({ theme: 'dark', resolvedTheme: 'dark', setTheme: setThemeFn })),
  };
});

vi.mock('@/features/shell/hooks/use-theme', () => ({ useTheme }));

vi.mock('next/navigation', () => ({ usePathname: () => '/scenarios' }));

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import { OperationsRail } from '@/features/shell/components/operations-rail';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

describe('OperationsRail theme toggle', () => {
  beforeEach(() => {
    setTheme.mockReset();
    useTheme.mockReturnValue({ theme: 'dark', resolvedTheme: 'dark', setTheme });
    useWorkspaceUiStore.getState().setPanelCollapsed('operationsRail', false);
  });
  afterEach(() => {
    cleanup();
  });

  it('renders the theme toggle with an accessible name when expanded', () => {
    render(<OperationsRail />);
    const toggle = screen.getByTestId('toggle-theme');
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAccessibleName(/theme/i);
  });

  it('flips the explicit preference to light when the resolved theme is dark', () => {
    render(<OperationsRail />);
    fireEvent.click(screen.getByTestId('toggle-theme'));
    expect(setTheme).toHaveBeenCalledWith('light');
  });

  it('flips the explicit preference to dark when the resolved theme is light', () => {
    useTheme.mockReturnValue({ theme: 'light', resolvedTheme: 'light', setTheme });
    render(<OperationsRail />);
    fireEvent.click(screen.getByTestId('toggle-theme'));
    expect(setTheme).toHaveBeenCalledWith('dark');
  });

  it('keeps an accessible name on the toggle when the rail is collapsed', () => {
    useWorkspaceUiStore.getState().setPanelCollapsed('operationsRail', true);
    render(<OperationsRail />);
    const toggle = screen.getByTestId('toggle-theme');
    expect(toggle).toHaveAccessibleName(/switch to (light|dark) theme/i);
  });
});

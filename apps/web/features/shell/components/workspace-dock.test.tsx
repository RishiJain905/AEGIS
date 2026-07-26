import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { WorkspaceDock } from './workspace-dock';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

const TABS = [
  { id: 'copilot', label: 'Copilot', content: <p>copilot body</p> },
  { id: 'evidence', label: 'Evidence', content: <p>evidence body</p> },
];

function renderDock() {
  return render(
    <WorkspaceDock
      region="leftDock"
      side="left"
      label="Operator console"
      data-testid="left-dock"
      tabs={TABS}
    />,
  );
}

beforeEach(() => {
  useWorkspaceUiStore.getState().setPanelCollapsed('leftDock', false);
});

afterEach(() => {
  cleanup();
  useWorkspaceUiStore.getState().setPanelCollapsed('leftDock', false);
});

describe('WorkspaceDock', () => {
  it('shows the first tab and switches to another on demand', async () => {
    const user = userEvent.setup();
    renderDock();

    expect(screen.getByText('copilot body')).toBeInTheDocument();
    expect(screen.queryByText('evidence body')).not.toBeInTheDocument();

    await user.click(screen.getByTestId('dock-tab-evidence'));
    expect(screen.getByText('evidence body')).toBeInTheDocument();
  });

  it('collapses to a strip and reopens straight to the tab that was clicked', async () => {
    const user = userEvent.setup();
    renderDock();

    await user.click(screen.getByTestId('collapse-leftDock'));
    expect(screen.getByTestId('left-dock-collapsed')).toBeInTheDocument();
    expect(screen.queryByText('copilot body')).not.toBeInTheDocument();
    expect(useWorkspaceUiStore.getState().panelPreferences.regions.leftDock?.collapsed).toBe(true);

    await user.click(screen.getByTestId('dock-strip-evidence'));
    expect(screen.getByText('evidence body')).toBeInTheDocument();
  });
});

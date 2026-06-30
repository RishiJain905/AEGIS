/**
 * @vitest-environment jsdom
 */
import { NodeStatus } from '@aegis/contracts-ts';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { Button, Badge, Dialog, DialogContent, DialogTitle, DialogTrigger } from '../../src';

describe('Button', () => {
  it('is keyboard activatable', async () => {
    const user = userEvent.setup();
    let clicked = false;
    render(
      <Button
        onClick={() => {
          clicked = true;
        }}
      >
        Activate
      </Button>,
    );
    const button = screen.getByRole('button', { name: 'Activate' });
    button.focus();
    await user.keyboard('{Enter}');
    expect(clicked).toBe(true);
  });
});

describe('Dialog', () => {
  it('opens and closes with keyboard', async () => {
    const user = userEvent.setup();
    render(
      <Dialog>
        <DialogTrigger asChild>
          <Button>Open</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogTitle>Test dialog</DialogTitle>
        </DialogContent>
      </Dialog>,
    );

    await user.click(screen.getByRole('button', { name: 'Open' }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

describe('Badge', () => {
  it('exposes accessible status label', () => {
    render(<Badge nodeStatus={NodeStatus.SUSPICIOUS} />);
    expect(screen.getByLabelText(/Status: Suspicious/)).toBeInTheDocument();
    expect(screen.getByText('Suspicious')).toBeInTheDocument();
  });
});

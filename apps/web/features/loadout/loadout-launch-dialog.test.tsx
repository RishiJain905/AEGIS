import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import { LoadoutLaunchDialog } from './loadout-launch-dialog';

const apiFetch = vi.fn();
vi.mock('@/lib/api/auth-fetch', () => ({
  apiFetch: (path: string, init?: RequestInit) => apiFetch(path, init) as unknown,
}));

const OPTIONS = [
  { id: 'openai-compatible', label: 'Local model', requiresCredential: false },
  { id: 'openai', label: 'OpenAI', requiresCredential: true },
];

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

/** A deployment offering the local model plus OpenAI, connected or not. */
function installApi({ openaiKeyHint }: { openaiKeyHint?: string } = {}) {
  const connected: Record<string, string> = openaiKeyHint ? { openai: openaiKeyHint } : {};
  apiFetch.mockImplementation((path: string, init?: RequestInit) => {
    const method = (init?.method ?? 'GET').toUpperCase();
    if (path === '/api/v1/providers/loadout-options') {
      return Promise.resolve(jsonResponse(200, OPTIONS));
    }
    if (path === '/api/v1/provider-credentials') {
      return Promise.resolve(
        jsonResponse(200, [
          connected.openai
            ? {
                schemaVersion: 1,
                provider: 'openai',
                configured: true,
                keyHint: connected.openai,
                verifiedAt: '2026-08-06T09:30:00Z',
              }
            : { schemaVersion: 1, provider: 'openai', configured: false },
        ]),
      );
    }
    if (path === '/api/v1/providers/openai/models') {
      return Promise.resolve(
        jsonResponse(200, {
          schemaVersion: 1,
          provider: 'openai',
          models: [{ id: 'gpt-4o', label: 'gpt-4o' }],
        }),
      );
    }
    if (path === '/api/v1/provider-credentials/openai' && method === 'PUT') {
      connected.openai = 'p99z';
      return Promise.resolve(
        jsonResponse(200, {
          schemaVersion: 1,
          provider: 'openai',
          configured: true,
          keyHint: 'p99z',
          verifiedAt: '2026-08-06T09:30:00Z',
        }),
      );
    }
    throw new Error(`Unexpected request: ${method} ${path}`);
  });
}

function Wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function renderDialog(onLaunch = vi.fn(), launching = false) {
  render(
    <Wrapper>
      <LoadoutLaunchDialog
        open
        onOpenChange={vi.fn()}
        scenarioName="Operation Silent Relay"
        launching={launching}
        onLaunch={onLaunch}
      />
    </Wrapper>,
  );
  return onLaunch;
}

beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false);
  Element.prototype.setPointerCapture = vi.fn();
  Element.prototype.releasePointerCapture = vi.fn();
  Element.prototype.scrollIntoView = vi.fn();
});

beforeEach(() => {
  installApi();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('LoadoutLaunchDialog', () => {
  it('launches with the default loadout (bias guard + threat tempo on, investigate)', async () => {
    const user = userEvent.setup();
    const onLaunch = renderDialog();
    await user.click(screen.getByTestId('loadout-launch-confirm'));
    expect(onLaunch).toHaveBeenCalledWith(
      {
        schemaVersion: 1,
        biasGuard: true,
        threatTempo: true,
        roe: 'investigate',
      },
      undefined,
    );
  });

  it('reflects toggling a capability off and choosing a different RoE', async () => {
    const user = userEvent.setup();
    const onLaunch = renderDialog();
    await user.click(screen.getByLabelText(/Bias guard/i));
    await user.click(screen.getByTestId('roe-option-forward_deployed'));
    await user.click(screen.getByTestId('loadout-launch-confirm'));
    expect(onLaunch).toHaveBeenCalledWith(
      {
        schemaVersion: 1,
        biasGuard: false,
        threatTempo: true,
        roe: 'forward_deployed',
      },
      undefined,
    );
  });

  it('passes a typed commander intent as the second onLaunch argument', async () => {
    const user = userEvent.setup();
    const onLaunch = renderDialog();
    const field = screen.getByTestId('loadout-commander-intent');
    expect(field).toHaveAttribute('maxLength', '280');
    await user.type(field, '  protect student records  ');
    await user.click(screen.getByTestId('loadout-launch-confirm'));
    expect(onLaunch).toHaveBeenCalledWith(expect.any(Object), 'protect student records');
  });

  it('passes undefined intent when the field is left blank', async () => {
    const user = userEvent.setup();
    const onLaunch = renderDialog();
    await user.click(screen.getByTestId('loadout-launch-confirm'));
    expect(onLaunch).toHaveBeenCalledWith(expect.any(Object), undefined);
  });
});

describe('LoadoutLaunchDialog — model provider', () => {
  it('blocks the launch while a cloud provider has no credential, and says why', async () => {
    const user = userEvent.setup();
    const onLaunch = renderDialog();

    await user.click(await screen.findByTestId('provider-option-openai'));

    const launch = screen.getByTestId('loadout-launch-confirm');
    expect(launch).toBeDisabled();
    expect(screen.getByTestId('loadout-launch-hint')).toHaveTextContent(/Connect OpenAI/i);
    expect(launch).toHaveAttribute(
      'aria-describedby',
      screen.getByTestId('loadout-launch-hint').id,
    );
    expect(onLaunch).not.toHaveBeenCalled();
  });

  it('still blocks the launch once connected but before a model is picked', async () => {
    const user = userEvent.setup();
    installApi({ openaiKeyHint: 'ab12' });
    renderDialog();

    await user.click(await screen.findByTestId('provider-option-openai'));
    await screen.findByTestId('provider-model-listbox');

    expect(screen.getByTestId('loadout-launch-confirm')).toBeDisabled();
    expect(screen.getByTestId('loadout-launch-hint')).toHaveTextContent(/pick a model/i);
  });

  it('carries providerId and modelId into the loadout once both are chosen', async () => {
    const user = userEvent.setup();
    installApi({ openaiKeyHint: 'ab12' });
    const onLaunch = renderDialog();

    await user.click(await screen.findByTestId('provider-option-openai'));
    await user.click(await screen.findByTestId('provider-model-option-gpt-4o'));
    await user.click(screen.getByTestId('loadout-launch-confirm'));

    expect(onLaunch).toHaveBeenCalledWith(
      {
        schemaVersion: 1,
        biasGuard: true,
        threatTempo: true,
        roe: 'investigate',
        providerId: 'openai',
        modelId: 'gpt-4o',
      },
      undefined,
    );
  });

  it('omits both provider fields when the run stays on the local model', async () => {
    const user = userEvent.setup();
    installApi({ openaiKeyHint: 'ab12' });
    const onLaunch = renderDialog();

    await user.click(await screen.findByTestId('provider-option-openai'));
    await user.click(await screen.findByTestId('provider-model-option-gpt-4o'));
    await user.click(screen.getByTestId('provider-option-openai-compatible'));
    await user.click(screen.getByTestId('loadout-launch-confirm'));

    // Deep equality: a provider field left behind by the detour would fail this.
    expect(onLaunch).toHaveBeenCalledWith(
      { schemaVersion: 1, biasGuard: true, threatTempo: true, roe: 'investigate' },
      undefined,
    );
    expect(screen.queryByTestId('loadout-launch-hint')).toBeNull();
  });
});

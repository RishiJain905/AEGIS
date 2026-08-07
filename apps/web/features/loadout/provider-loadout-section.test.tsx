import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import { ProviderLoadoutSection } from './provider-loadout-section';
import { DEFAULT_PROVIDER_SELECTION, type ProviderSelection } from './use-provider-credentials';

const apiFetch = vi.fn();
vi.mock('@/lib/api/auth-fetch', () => ({
  apiFetch: (path: string, init?: RequestInit) => apiFetch(path, init) as unknown,
}));

const OPTIONS = [
  { id: 'openai-compatible', label: 'Local model', requiresCredential: false },
  { id: 'openai', label: 'OpenAI', requiresCredential: true },
  { id: 'openrouter', label: 'OpenRouter', requiresCredential: true },
  { id: 'ollama-cloud', label: 'Ollama Cloud', requiresCredential: true },
];

const CLOUD_PROVIDERS = ['openai', 'openrouter', 'ollama-cloud'];

interface HttpFailure {
  status: number;
  detail: string;
}

interface FakeApi {
  /** provider id → key hint, i.e. the credentials this account has stored. */
  connected: Record<string, string>;
  models: Record<string, { id: string; label: string }[]>;
  connectFailure?: HttpFailure;
  disconnectFailure?: HttpFailure;
  modelsFailure?: HttpFailure;
  optionsFailure?: HttpFailure;
  calls: { path: string; method: string; body?: string }[];
}

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

function credentialStatus(provider: string, keyHint: string | undefined) {
  return keyHint === undefined
    ? { schemaVersion: 1, provider, configured: false, keyHint: null, verifiedAt: null }
    : {
        schemaVersion: 1,
        provider,
        configured: true,
        keyHint,
        verifiedAt: '2026-08-06T09:30:00Z',
      };
}

function installApi(overrides: Partial<FakeApi> = {}): FakeApi {
  const api: FakeApi = {
    connected: {},
    models: {
      openai: [
        { id: 'gpt-4o', label: 'gpt-4o' },
        { id: 'gpt-4o-mini', label: 'gpt-4o-mini' },
      ],
      // OpenRouter fronts hundreds of models; ten is enough to earn the filter field.
      openrouter: [
        'anthropic/claude-sonnet-4',
        'anthropic/claude-opus-4',
        'google/gemini-2.5-pro',
        'meta-llama/llama-3.3-70b',
        'mistralai/mistral-large',
        'openai/gpt-4o',
        'openai/gpt-4o-mini',
        'qwen/qwen-2.5-72b',
        'x-ai/grok-3',
        'deepseek/deepseek-r1',
      ].map((id) => ({ id, label: id })),
      'ollama-cloud': [{ id: 'gpt-oss:120b', label: 'gpt-oss:120b' }],
    },
    calls: [],
    ...overrides,
  };

  apiFetch.mockImplementation((path: string, init?: RequestInit) => {
    const method = (init?.method ?? 'GET').toUpperCase();
    api.calls.push({ path, method, body: init?.body as string | undefined });

    if (path === '/api/v1/providers/loadout-options') {
      return Promise.resolve(
        api.optionsFailure
          ? jsonResponse(api.optionsFailure.status, { detail: api.optionsFailure.detail })
          : jsonResponse(200, OPTIONS),
      );
    }
    if (path === '/api/v1/provider-credentials') {
      return Promise.resolve(
        jsonResponse(
          200,
          CLOUD_PROVIDERS.map((provider) => credentialStatus(provider, api.connected[provider])),
        ),
      );
    }

    const credential = /^\/api\/v1\/provider-credentials\/([^/]+)$/.exec(path);
    if (credential) {
      const provider = decodeURIComponent(credential[1] ?? '');
      if (method === 'PUT') {
        if (api.connectFailure) {
          return Promise.resolve(
            jsonResponse(api.connectFailure.status, { detail: api.connectFailure.detail }),
          );
        }
        api.connected[provider] = 'p99z';
        return Promise.resolve(jsonResponse(200, credentialStatus(provider, 'p99z')));
      }
      if (method === 'DELETE') {
        if (api.disconnectFailure) {
          return Promise.resolve(
            jsonResponse(api.disconnectFailure.status, { detail: api.disconnectFailure.detail }),
          );
        }
        Reflect.deleteProperty(api.connected, provider);
        return Promise.resolve(jsonResponse(204, null));
      }
    }

    const models = /^\/api\/v1\/providers\/([^/]+)\/models$/.exec(path);
    if (models) {
      const provider = decodeURIComponent(models[1] ?? '');
      if (api.modelsFailure) {
        return Promise.resolve(
          jsonResponse(api.modelsFailure.status, { detail: api.modelsFailure.detail }),
        );
      }
      return Promise.resolve(
        jsonResponse(200, { schemaVersion: 1, provider, models: api.models[provider] ?? [] }),
      );
    }

    throw new Error(`Unexpected request: ${method} ${path}`);
  });

  return api;
}

function renderSection(initial: ProviderSelection = DEFAULT_PROVIDER_SELECTION) {
  const onSelectionChange = vi.fn();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  function Harness() {
    const [selection, setSelection] = useState<ProviderSelection>(initial);
    return (
      <QueryClientProvider client={client}>
        <ProviderLoadoutSection
          selection={selection}
          active
          onSelectionChange={(next) => {
            onSelectionChange(next);
            setSelection(next);
          }}
        />
      </QueryClientProvider>
    );
  }

  return { ...render(<Harness />), onSelectionChange };
}

/** axe with contrast off: the palette is CSS custom properties jsdom never loads. */
async function expectNoAxeViolations(container: HTMLElement) {
  const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } });
  expect(results.violations).toHaveLength(0);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  installApi();
});

describe('ProviderLoadoutSection — provider choice', () => {
  it('renders one radio card per offered provider with the local model selected', async () => {
    renderSection();

    await screen.findByTestId('provider-option-openai-compatible');
    const group = screen.getByRole('radiogroup', { name: /AI model provider/i });
    const cards = within(group).getAllByRole('radio');
    expect(cards).toHaveLength(4);
    expect(screen.getByTestId('provider-option-openai-compatible')).toHaveAttribute(
      'aria-checked',
      'true',
    );
    expect(screen.getByTestId('provider-option-openai')).toHaveAttribute('aria-checked', 'false');
  });

  it('asks for nothing more when the local model is selected', async () => {
    renderSection();

    await screen.findByTestId('provider-option-openai-compatible');
    expect(screen.queryByTestId('provider-api-key')).toBeNull();
    expect(screen.queryByTestId('provider-model-listbox')).toBeNull();
  });

  it('reports the picked provider upward and clears any previously picked model', async () => {
    const user = userEvent.setup();
    const { onSelectionChange } = renderSection({
      providerId: 'openai',
      modelId: 'gpt-4o',
      requiresCredential: true,
    });

    await user.click(await screen.findByTestId('provider-option-openai-compatible'));

    expect(onSelectionChange).toHaveBeenCalledWith({
      providerId: 'openai-compatible',
      modelId: null,
      requiresCredential: false,
    });
  });

  it('surfaces a failure to load the provider list without hiding the section', async () => {
    installApi({ optionsFailure: { status: 502, detail: 'upstream is down' } });
    renderSection();

    expect(await screen.findByTestId('provider-error')).toHaveTextContent(/could not/i);
  });
});

describe('ProviderLoadoutSection — connecting a key', () => {
  it('offers a masked key field for a cloud provider with no stored credential', async () => {
    const user = userEvent.setup();
    renderSection();

    await user.click(await screen.findByTestId('provider-option-openai'));

    const field = await screen.findByTestId('provider-api-key');
    expect(field).toHaveAttribute('type', 'password');
    expect(field).toHaveAttribute('autocomplete', 'off');
    expect(screen.getByTestId('provider-connect')).toBeDisabled();
  });

  it('verifies and stores the key, then shows only the hint and the model picker', async () => {
    const user = userEvent.setup();
    const api = installApi();
    renderSection();

    await user.click(await screen.findByTestId('provider-option-openai'));
    await user.type(await screen.findByTestId('provider-api-key'), 'sk-live-secret-p99z');
    await user.click(screen.getByTestId('provider-connect'));

    expect(await screen.findByTestId('provider-connected')).toHaveTextContent('…p99z');
    const put = api.calls.find((call) => call.method === 'PUT');
    expect(put?.path).toBe('/api/v1/provider-credentials/openai');
    expect(put?.body).toBe(JSON.stringify({ apiKey: 'sk-live-secret-p99z' }));

    // The key itself is gone from the DOM the moment it is stored.
    expect(screen.queryByTestId('provider-api-key')).toBeNull();
    expect(document.body.textContent).not.toContain('sk-live-secret-p99z');
    await screen.findByTestId('provider-model-listbox');
  });

  it('shows a rejected key as the provider classified it, and keeps the field', async () => {
    const user = userEvent.setup();
    installApi({
      connectFailure: { status: 400, detail: 'OpenAI rejected the API key (incorrect_api_key)' },
    });
    renderSection();

    await user.click(await screen.findByTestId('provider-option-openai'));
    await user.type(await screen.findByTestId('provider-api-key'), 'sk-wrong');
    await user.click(screen.getByTestId('provider-connect'));

    expect(await screen.findByTestId('provider-error')).toHaveTextContent(
      'OpenAI rejected the API key (incorrect_api_key)',
    );
    expect(screen.getByTestId('provider-api-key')).toBeInTheDocument();
    expect(screen.queryByTestId('provider-connected')).toBeNull();
  });

  it('distinguishes an unreachable provider from a rejected key', async () => {
    const user = userEvent.setup();
    installApi({ connectFailure: { status: 502, detail: 'provider timed out' } });
    renderSection();

    await user.click(await screen.findByTestId('provider-option-openrouter'));
    await user.type(await screen.findByTestId('provider-api-key'), 'sk-or-key');
    await user.click(screen.getByTestId('provider-connect'));

    expect(await screen.findByTestId('provider-error')).toHaveTextContent(
      /OpenRouter could not be reached/i,
    );
  });

  it('names the deployment, not the key, when the server cannot store credentials', async () => {
    const user = userEvent.setup();
    installApi({
      connectFailure: { status: 503, detail: 'AEGIS_CREDENTIAL_ENCRYPTION_KEY is unset.' },
    });
    renderSection();

    await user.click(await screen.findByTestId('provider-option-openai'));
    await user.type(await screen.findByTestId('provider-api-key'), 'sk-live');
    await user.click(screen.getByTestId('provider-connect'));

    expect(await screen.findByTestId('provider-error')).toHaveTextContent(
      /not configured for cloud model providers/i,
    );
  });

  it('says so when the operator may not store credentials at all', async () => {
    const user = userEvent.setup();
    installApi({ connectFailure: { status: 403, detail: 'Forbidden' } });
    renderSection();

    await user.click(await screen.findByTestId('provider-option-openai'));
    await user.type(await screen.findByTestId('provider-api-key'), 'sk-live');
    await user.click(screen.getByTestId('provider-connect'));

    expect(await screen.findByTestId('provider-error')).toHaveTextContent(
      /account is not allowed/i,
    );
  });
});

describe('ProviderLoadoutSection — a connected provider', () => {
  it('lists the provider models and reports the picked one upward', async () => {
    const user = userEvent.setup();
    installApi({ connected: { openrouter: 'ab12' } });
    const { onSelectionChange } = renderSection();

    await user.click(await screen.findByTestId('provider-option-openrouter'));
    expect(await screen.findByTestId('provider-connected')).toHaveTextContent('…ab12');

    const listbox = await screen.findByTestId('provider-model-listbox');
    expect(within(listbox).getAllByRole('option')).toHaveLength(10);
    await user.click(screen.getByTestId('provider-model-option-openai/gpt-4o'));

    expect(onSelectionChange).toHaveBeenLastCalledWith({
      providerId: 'openrouter',
      modelId: 'openai/gpt-4o',
      requiresCredential: true,
    });
    expect(screen.getByTestId('provider-model-option-openai/gpt-4o')).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });

  it('filters the model list as the operator types', async () => {
    const user = userEvent.setup();
    installApi({ connected: { openrouter: 'ab12' } });
    renderSection();

    await user.click(await screen.findByTestId('provider-option-openrouter'));
    await user.type(await screen.findByTestId('provider-model-filter'), 'llama');

    const listbox = screen.getByTestId('provider-model-listbox');
    expect(within(listbox).getAllByRole('option')).toHaveLength(1);
    expect(listbox).toHaveTextContent('meta-llama/llama-3.3-70b');
  });

  it('says when a filter matches nothing rather than showing an empty box', async () => {
    const user = userEvent.setup();
    installApi({ connected: { openrouter: 'ab12' } });
    renderSection();

    await user.click(await screen.findByTestId('provider-option-openrouter'));
    await user.type(await screen.findByTestId('provider-model-filter'), 'zzzz');

    expect(screen.getByTestId('provider-models-empty')).toHaveTextContent(/no model/i);
  });

  it('spares a short catalogue the filter field it does not need', async () => {
    const user = userEvent.setup();
    installApi({ connected: { openai: 'ab12' } });
    renderSection();

    await user.click(await screen.findByTestId('provider-option-openai'));
    await screen.findByTestId('provider-model-listbox');
    expect(screen.queryByTestId('provider-model-filter')).toBeNull();
  });

  it('offers a retry when the catalogue cannot be fetched', async () => {
    const user = userEvent.setup();
    const api = installApi({
      connected: { openai: 'ab12' },
      modelsFailure: { status: 502, detail: 'provider timed out' },
    });
    renderSection();

    await user.click(await screen.findByTestId('provider-option-openai'));
    expect(await screen.findByTestId('provider-error')).toHaveTextContent(
      /OpenAI could not be reached/i,
    );

    api.modelsFailure = undefined;
    await user.click(screen.getByTestId('provider-models-retry'));
    await screen.findByTestId('provider-model-listbox');
  });

  it('replaces a key without ever redisplaying the stored one', async () => {
    const user = userEvent.setup();
    installApi({ connected: { openai: 'ab12' } });
    renderSection();

    await user.click(await screen.findByTestId('provider-option-openai'));
    await user.click(await screen.findByTestId('provider-replace-key'));

    const field = screen.getByTestId('provider-api-key');
    expect(field).toHaveValue('');
    expect(field).toHaveAttribute('type', 'password');
    // "Replace key" destroys the button that had focus; the field it opened takes it.
    expect(field).toHaveFocus();

    await user.click(screen.getByTestId('provider-replace-cancel'));
    expect(screen.queryByTestId('provider-api-key')).toBeNull();
    expect(screen.getByTestId('provider-connected')).toHaveTextContent('…ab12');
  });

  it('drops the model along with the credential on disconnect', async () => {
    const user = userEvent.setup();
    installApi({ connected: { openai: 'ab12' } });
    const { onSelectionChange } = renderSection();

    await user.click(await screen.findByTestId('provider-option-openai'));
    await user.click(await screen.findByTestId('provider-model-option-gpt-4o'));
    await user.click(screen.getByTestId('provider-disconnect'));

    await waitFor(() => {
      expect(screen.getByTestId('provider-api-key')).toBeInTheDocument();
    });
    expect(screen.getByTestId('provider-api-key')).toHaveFocus();
    expect(onSelectionChange).toHaveBeenLastCalledWith({
      providerId: 'openai',
      modelId: null,
      requiresCredential: true,
    });
  });

  it('leaves no focus claim behind when the disconnect fails', async () => {
    const user = userEvent.setup();
    installApi({
      connected: { openai: 'ab12' },
      disconnectFailure: { status: 403, detail: 'Forbidden' },
    });
    renderSection();

    await user.click(await screen.findByTestId('provider-option-openai'));
    await user.click(await screen.findByTestId('provider-disconnect'));
    expect(await screen.findByTestId('provider-error')).toBeInTheDocument();

    // The provider is still connected, so no key field opened and nothing took focus.
    // Moving to a provider that *does* need one must not inherit the abandoned claim:
    // stealing focus out of the radiogroup would break arrow-key navigation between cards.
    const openrouter = screen.getByTestId('provider-option-openrouter');
    await user.click(openrouter);
    await screen.findByTestId('provider-api-key');
    expect(screen.getByTestId('provider-api-key')).not.toHaveFocus();
    expect(openrouter).toHaveFocus();
  });
});

describe('ProviderLoadoutSection — accessibility', () => {
  it('has no axe violations with the local model selected', async () => {
    const { container } = renderSection();
    await screen.findByTestId('provider-option-openai-compatible');
    await expectNoAxeViolations(container);
  });

  it('has no axe violations while asking for a key', async () => {
    const user = userEvent.setup();
    const { container } = renderSection();
    await user.click(await screen.findByTestId('provider-option-openai'));
    await screen.findByTestId('provider-api-key');
    await expectNoAxeViolations(container);
  });

  it('has no axe violations while reporting a rejected key', async () => {
    const user = userEvent.setup();
    installApi({ connectFailure: { status: 400, detail: 'rejected' } });
    const { container } = renderSection();
    await user.click(await screen.findByTestId('provider-option-openai'));
    await user.type(await screen.findByTestId('provider-api-key'), 'sk-wrong');
    await user.click(screen.getByTestId('provider-connect'));
    await screen.findByTestId('provider-error');
    await expectNoAxeViolations(container);
  });

  it('has no axe violations with a connected provider and a picked model', async () => {
    const user = userEvent.setup();
    installApi({ connected: { openai: 'ab12' } });
    const { container } = renderSection();
    await user.click(await screen.findByTestId('provider-option-openai'));
    await user.click(await screen.findByTestId('provider-model-option-gpt-4o'));
    await expectNoAxeViolations(container);
  });

  it('keeps one tab stop in the model list and moves the pick with the arrow keys', async () => {
    const user = userEvent.setup();
    installApi({ connected: { openrouter: 'ab12' } });
    const { onSelectionChange } = renderSection();

    await user.click(await screen.findByTestId('provider-option-openrouter'));
    const listbox = await screen.findByTestId('provider-model-listbox');
    const options = within(listbox).getAllByRole('option');
    expect(options.filter((option) => option.getAttribute('tabindex') === '0')).toHaveLength(1);

    options[0]?.focus();
    await user.keyboard('{ArrowDown}');
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ modelId: 'anthropic/claude-opus-4' }),
    );
  });
});

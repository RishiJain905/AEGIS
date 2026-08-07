'use client';

import {
  loadoutProviderOptionSchema,
  parseContract,
  providerCredentialStatusSchema,
  providerModelListSchema,
  type LoadoutProviderOptionV1,
  type ProviderCredentialStatusV1,
  type ProviderModelListV1,
} from '@aegis/contracts-ts';
import { useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query';
import { useCallback, useState } from 'react';

import { LOCAL_PROVIDER_ID, providerDoctrine } from '@/features/command-surface/contracts';
import { apiFetch } from '@/lib/api/auth-fetch';
import { queryKeys } from '@/lib/api/query-keys';
import { ApiClientError } from '@/lib/api/types';

/**
 * The console side of per-user model-provider credentials: which providers a run may be
 * launched on, which of them this operator has connected, and the catalogue each one offers.
 *
 * One rule governs the whole module. **A plaintext API key never enters shared state.** It
 * is an argument to `connect`, it is a request body, and that is the end of it — hence the
 * hand-rolled action hook below instead of `useMutation`, whose variables would park the key
 * in the global mutation cache (and any devtools reading it) long after the dialog closed.
 * The only fragment that is ever cached or rendered is `keyHint`, the last four characters.
 */

/** One provider the launch dialog can offer, and whether the run needs a key for it. */
export type LoadoutProviderOption = LoadoutProviderOptionV1;
/** Whether this operator has a usable key for one provider — never the key. */
export type ProviderCredentialStatus = ProviderCredentialStatusV1;

/** What the loadout dialog carries about the model a run will generate on. */
export interface ProviderSelection {
  providerId: string;
  /** The pinned model, or null when none has been picked yet. */
  modelId: string | null;
  /** Whether this provider needs a stored key before the run can launch. */
  requiresCredential: boolean;
}

export const DEFAULT_PROVIDER_SELECTION: ProviderSelection = {
  providerId: LOCAL_PROVIDER_ID,
  modelId: null,
  requiresCredential: false,
};

/**
 * The provider fields to merge into the submitted loadout — nothing at all for the local
 * default, matching the omit-don't-null convention the create-run body already follows.
 */
export function providerLoadoutFields(selection: ProviderSelection): {
  providerId?: string;
  modelId?: string;
} {
  if (!selection.requiresCredential || selection.modelId === null) {
    return {};
  }
  return { providerId: selection.providerId, modelId: selection.modelId };
}

/**
 * Two list endpoints, validated one element at a time. `z.array()` over these object schemas
 * blows TypeScript's instantiation depth in the app's strict project, and per-element parsing
 * gives the same guarantee — every element is a real contract instance — with a clearer
 * failure when the server sends something else entirely.
 */
function parseList<T>(data: unknown, parseItem: (item: unknown) => T): T[] {
  if (!Array.isArray(data)) {
    throw new ApiClientError({
      code: 'CONTRACT_VALIDATION_FAILED',
      message: 'The model-provider API answered with something other than a list',
      status: 500,
    });
  }
  return (data as unknown[]).map(parseItem);
}

/** A catalogue is fetched from the provider itself, so it is worth holding for a while. */
const CATALOGUE_STALE_TIME_MS = 5 * 60 * 1000;

/**
 * The credential routes answer failures with FastAPI's `{detail}` rather than the platform
 * error envelope, and that detail is the provider's own classified complaint — the most
 * actionable thing an operator can be told. Read it, falling back to `message` for the
 * routes that do carry an envelope.
 */
async function readProviderError(response: Response): Promise<ApiClientError> {
  let message: string | undefined;
  try {
    const body: unknown = await response.json();
    if (typeof body === 'object' && body !== null) {
      const envelope = body as { detail?: unknown; message?: unknown };
      if (typeof envelope.detail === 'string') {
        message = envelope.detail;
      } else if (typeof envelope.message === 'string') {
        message = envelope.message;
      }
    }
  } catch {
    message = undefined;
  }
  return new ApiClientError({
    code: 'HTTP_ERROR',
    message: message ?? `Request failed with status ${String(response.status)}`,
    status: response.status,
  });
}

async function providerRequest<T>(
  path: string,
  init: RequestInit,
  parse: (data: unknown) => T,
): Promise<T> {
  const response = await apiFetch(path, init);
  if (!response.ok) {
    throw await readProviderError(response);
  }
  if (response.status === 204) {
    return parse(undefined);
  }
  const body: unknown = await response.json();
  return parse(body);
}

/** The providers this deployment offers, in the order the dialog should show them. */
export function useLoadoutProviderOptions(
  enabled: boolean,
): UseQueryResult<LoadoutProviderOption[]> {
  return useQuery({
    queryKey: queryKeys.providers.loadoutOptions,
    queryFn: ({ signal }) =>
      providerRequest('/api/v1/providers/loadout-options', { signal }, (data) =>
        parseList(data, (item) => parseContract(loadoutProviderOptionSchema, item)),
      ),
    enabled,
    staleTime: CATALOGUE_STALE_TIME_MS,
  });
}

/**
 * Which cloud providers this operator has connected. Deliberately not cached across dialog
 * openings: a key can be revoked from another tab, and a stale "connected" would let the
 * operator launch into a generation failure.
 */
export function useProviderCredentials(
  enabled: boolean,
): UseQueryResult<ProviderCredentialStatus[]> {
  return useQuery({
    queryKey: queryKeys.providers.credentials,
    queryFn: ({ signal }) =>
      providerRequest('/api/v1/provider-credentials', { signal }, (data) =>
        parseList(data, (item) => parseContract(providerCredentialStatusSchema, item)),
      ),
    enabled,
  });
}

/** One provider's live catalogue, fetched on this operator's stored key. */
export function useProviderModels(
  providerId: string | null,
  enabled: boolean,
): UseQueryResult<ProviderModelListV1> {
  return useQuery({
    queryKey: queryKeys.providers.models(providerId ?? ''),
    queryFn: ({ signal }) =>
      providerRequest(
        `/api/v1/providers/${encodeURIComponent(providerId ?? '')}/models`,
        { signal },
        (data) => parseContract(providerModelListSchema, data),
      ),
    enabled: enabled && providerId !== null,
    // Listing reaches the provider itself. A failure gets a retry affordance the operator
    // presses, rather than an automatic retry storm against someone else's rate limit.
    retry: false,
    staleTime: CATALOGUE_STALE_TIME_MS,
  });
}

export interface ProviderCredentialActions {
  /** Verify and store a key. Resolves true when it was accepted. */
  connect: (providerId: string, apiKey: string) => Promise<boolean>;
  /** Forget the stored key for one provider. Resolves true when it is gone. */
  disconnect: (providerId: string) => Promise<boolean>;
  pending: boolean;
  error: unknown;
  clearError: () => void;
}

/**
 * Connect/disconnect as plain awaited calls with local status, not `useMutation`.
 *
 * A mutation would keep its variables — here, the operator's plaintext API key — in the
 * global mutation cache for the whole garbage-collection window, readable by anything that
 * inspects it. Local state dies with the dialog, so the key exists only for the duration of
 * the request.
 */
export function useProviderCredentialActions(): ProviderCredentialActions {
  const queryClient = useQueryClient();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const run = useCallback(async (work: () => Promise<void>): Promise<boolean> => {
    setPending(true);
    setError(null);
    try {
      await work();
      return true;
    } catch (caught) {
      setError(caught);
      return false;
    } finally {
      setPending(false);
    }
  }, []);

  const connect = useCallback(
    (providerId: string, apiKey: string) =>
      run(async () => {
        await providerRequest(
          `/api/v1/provider-credentials/${encodeURIComponent(providerId)}`,
          {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ apiKey }),
          },
          (data) => parseContract(providerCredentialStatusSchema, data),
        );
        await queryClient.invalidateQueries({ queryKey: queryKeys.providers.credentials });
        // A new key may reach a different catalogue than the one it replaced.
        await queryClient.invalidateQueries({ queryKey: queryKeys.providers.models(providerId) });
      }),
    [queryClient, run],
  );

  const disconnect = useCallback(
    (providerId: string) =>
      run(async () => {
        await providerRequest(
          `/api/v1/provider-credentials/${encodeURIComponent(providerId)}`,
          { method: 'DELETE' },
          () => undefined,
        );
        await queryClient.invalidateQueries({ queryKey: queryKeys.providers.credentials });
        // Drop the catalogue outright: without a key there is nothing left to list.
        queryClient.removeQueries({ queryKey: queryKeys.providers.models(providerId) });
      }),
    [queryClient, run],
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return { connect, disconnect, pending, error, clearError };
}

/**
 * One failure, said in a way the operator can act on. The status is what separates "your key
 * is wrong" from "the provider is down" from "this deployment cannot store keys at all" —
 * three failures with three different fixes, and only one of them the operator's.
 *
 * Takes the provider's id as well as its label because the server writes its complaints
 * against the wire id, and the operator has only ever seen the label.
 */
export function describeProviderError(
  error: unknown,
  provider: { id: string; label: string },
): string {
  const { id, label } = provider;
  if (!(error instanceof ApiClientError)) {
    return `${label} could not be reached from this console. Check your connection and try again.`;
  }
  switch (error.status) {
    case 400:
      // The provider's own classification, already redacted server-side — but phrased
      // against the wire id: `Provider 'ollama-cloud' rejected the API key`. The
      // operator picked a card labelled "Ollama Cloud"; say it back to them in the
      // words they chose. The two-step swap drops the redundant "Provider" where the
      // message leads with it, and still names the label anywhere else it appears.
      return error.message.replaceAll(`Provider '${id}'`, label).replaceAll(`'${id}'`, label);
    case 401:
    case 403:
      return 'Your account is not allowed to connect model-provider keys. Ask an administrator for run-launch permission.';
    case 404:
      return `This deployment does not offer ${label}.`;
    case 503:
      return 'This deployment is not configured for cloud model providers. An administrator has to set a credential encryption key before any key can be stored.';
    default:
      return `${label} could not be reached (${String(error.status)}). Try again in a moment.`;
  }
}

/**
 * Why the run cannot launch on the current selection yet, or null when it can. The local
 * model never blocks; a cloud provider needs a stored key first and then a chosen model.
 */
export function useProviderLaunchBlock(
  selection: ProviderSelection,
  active: boolean,
): string | null {
  const optionsQuery = useLoadoutProviderOptions(active);
  const credentialsQuery = useProviderCredentials(active);

  if (!selection.requiresCredential) {
    return null;
  }
  const label =
    optionsQuery.data?.find((option) => option.id === selection.providerId)?.label ??
    providerDoctrine(selection.providerId).label;
  const connected =
    credentialsQuery.data?.some(
      (status) => status.provider === selection.providerId && status.configured,
    ) ?? false;
  if (!connected) {
    return `Connect ${label} to launch this run on it.`;
  }
  if (selection.modelId === null) {
    return `Pick a model to launch this run on ${label}.`;
  }
  return null;
}

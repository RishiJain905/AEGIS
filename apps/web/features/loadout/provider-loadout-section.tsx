'use client';

import { Button, cn } from '@aegis/ui';
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react';

import { providerDoctrine } from '@/features/command-surface/contracts';

import {
  describeProviderError,
  useLoadoutProviderOptions,
  useProviderCredentialActions,
  useProviderCredentials,
  useProviderModels,
  type ProviderSelection,
} from './use-provider-credentials';

const FIELD_CLASS =
  'min-w-0 flex-1 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-base)] px-3 py-2 font-mono text-xs text-[var(--aegis-text-primary)] placeholder:text-[var(--aegis-text-faint)] focus:border-[var(--aegis-border-strong)] focus:outline-none disabled:opacity-50';

const CAPTION_CLASS = 'text-[10px] leading-4 text-[var(--aegis-text-faint)]';

const LABEL_CLASS = 'font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]';

/** Above this many models the list stops being scannable and earns a filter field. */
const MODEL_FILTER_THRESHOLD = 8;

function ErrorLine({ children }: { children: React.ReactNode }) {
  return (
    <p
      role="alert"
      data-testid="provider-error"
      className="flex flex-wrap items-center gap-2 text-[11px] leading-4 text-[var(--aegis-risk-critical)]"
    >
      {children}
    </p>
  );
}

/**
 * Single-select model listbox with the standard roving tab stop: one option is reachable by
 * Tab and the arrow keys move both focus and the selection. OpenRouter lists hundreds of
 * models — a tab stop per option would be a keyboard trap in all but name.
 */
function ModelListbox({
  listboxId,
  models,
  selectedId,
  onSelect,
  disabled,
}: {
  listboxId: string;
  models: { id: string; label: string }[];
  selectedId: string | null;
  onSelect: (modelId: string) => void;
  disabled: boolean;
}) {
  const optionRefs = useRef<(HTMLDivElement | null)[]>([]);
  const selectedIndex = models.findIndex((model) => model.id === selectedId);
  const tabStopIndex = selectedIndex >= 0 ? selectedIndex : 0;

  const moveTo = (index: number) => {
    const clamped = Math.min(models.length - 1, Math.max(0, index));
    const model = models[clamped];
    if (!model || disabled) {
      return;
    }
    onSelect(model.id);
    optionRefs.current[clamped]?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>, index: number) => {
    const model = models[index];
    switch (event.key) {
      case 'ArrowDown':
      case 'ArrowRight':
        event.preventDefault();
        moveTo(index + 1);
        break;
      case 'ArrowUp':
      case 'ArrowLeft':
        event.preventDefault();
        moveTo(index - 1);
        break;
      case 'Home':
        event.preventDefault();
        moveTo(0);
        break;
      case 'End':
        event.preventDefault();
        moveTo(models.length - 1);
        break;
      case 'Enter':
      case ' ':
        event.preventDefault();
        if (model && !disabled) {
          onSelect(model.id);
        }
        break;
      default:
        break;
    }
  };

  return (
    <div
      id={listboxId}
      role="listbox"
      aria-label="Model"
      data-testid="provider-model-listbox"
      className="max-h-40 overflow-y-auto rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-base)]"
    >
      {models.map((model, index) => {
        const selected = model.id === selectedId;
        return (
          <div
            key={model.id}
            role="option"
            aria-selected={selected}
            tabIndex={index === tabStopIndex ? 0 : -1}
            ref={(node) => {
              optionRefs.current[index] = node;
            }}
            data-testid={`provider-model-option-${model.id}`}
            onClick={() => {
              if (!disabled) {
                onSelect(model.id);
              }
            }}
            onKeyDown={(event) => {
              handleKeyDown(event, index);
            }}
            className={cn(
              'cursor-pointer truncate px-3 py-1.5 font-mono text-xs transition-colors focus:outline-none',
              selected
                ? 'bg-[var(--aegis-accent-soft)] text-[var(--aegis-accent-strong)]'
                : 'text-[var(--aegis-text-secondary)] hover:bg-[var(--aegis-surface-hover)] focus:bg-[var(--aegis-surface-hover)]',
            )}
          >
            {model.label}
          </div>
        );
      })}
    </div>
  );
}

export interface ProviderLoadoutSectionProps {
  selection: ProviderSelection;
  onSelectionChange: (selection: ProviderSelection) => void;
  /** Query only while the section is on screen — the dialog is mounted, not always open. */
  active: boolean;
  /** The run is already launching; freeze the controls. */
  disabled?: boolean;
}

/**
 * "AI model provider" — which model drives every agent generation in the run about to
 * launch. The local endpoint needs nothing; a cloud provider needs the operator's own key
 * (verified and stored server-side, once) and then a model chosen from its live catalogue.
 *
 * The key field is write-only by construction: it is masked, it is never populated from
 * anything the server returns, and it is emptied the moment the key is accepted. The only
 * thing this section ever displays about a stored credential is its last four characters.
 */
export function ProviderLoadoutSection({
  selection,
  onSelectionChange,
  active,
  disabled = false,
}: ProviderLoadoutSectionProps) {
  const keyFieldId = useId();
  const keyHelpId = useId();
  const listboxId = useId();

  const optionsQuery = useLoadoutProviderOptions(active);
  const credentialsQuery = useProviderCredentials(active);
  const { connect, disconnect, pending, error, clearError } = useProviderCredentialActions();

  const [apiKey, setApiKey] = useState('');
  const [replacing, setReplacing] = useState(false);
  const [filter, setFilter] = useState('');
  const keyFieldRef = useRef<HTMLInputElement | null>(null);
  // Replacing and disconnecting both destroy the button that was focused. Set this and the
  // field they open takes the focus, instead of dropping the operator onto <body>.
  const claimKeyFieldFocus = useRef(false);

  const options = optionsQuery.data ?? [];
  const selectedOption = options.find((option) => option.id === selection.providerId);
  const providerLabel = selectedOption?.label ?? providerDoctrine(selection.providerId).label;

  const credential = credentialsQuery.data?.find(
    (status) => status.provider === selection.providerId,
  );
  const connected = credential?.configured === true;
  const needsCredential = selection.requiresCredential;

  const modelsQuery = useProviderModels(
    needsCredential && connected ? selection.providerId : null,
    active,
  );

  // Nothing about one provider survives a move to another — a pending focus claim least of
  // all, since selecting a card must leave focus on the card the operator is arrowing through.
  useEffect(() => {
    setApiKey('');
    setReplacing(false);
    setFilter('');
    claimKeyFieldFocus.current = false;
    clearError();
  }, [selection.providerId, clearError]);

  const models = modelsQuery.data?.models ?? [];
  const filtered = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (needle.length === 0) {
      return models;
    }
    return models.filter(
      (model) =>
        model.id.toLowerCase().includes(needle) || model.label.toLowerCase().includes(needle),
    );
  }, [models, filter]);

  const selectProvider = (providerId: string, requiresCredential: boolean) => {
    if (providerId === selection.providerId) {
      return;
    }
    onSelectionChange({ providerId, modelId: null, requiresCredential });
  };

  const handleConnect = async () => {
    const candidate = apiKey.trim();
    if (candidate.length === 0) {
      return;
    }
    const stored = await connect(selection.providerId, candidate);
    if (stored) {
      setApiKey('');
      setReplacing(false);
    }
  };

  const handleDisconnect = async () => {
    // Claimed before the await, not after: disconnecting refetches the credential list, and
    // the render that flips `showKeyForm` — the one the focus effect watches — can commit
    // before this continuation resumes. A claim staked afterwards would arrive too late and
    // never fire again, since a ref cannot re-trigger the effect.
    claimKeyFieldFocus.current = true;
    const forgotten = await disconnect(selection.providerId);
    if (forgotten) {
      setApiKey('');
      setReplacing(false);
      onSelectionChange({ ...selection, modelId: null });
      return;
    }
    // The key is still stored, so no field opened and nothing lost focus. Drop the claim:
    // left standing it would fire on the next unrelated open — moving to another provider
    // would yank focus out of the radiogroup mid arrow-key navigation.
    claimKeyFieldFocus.current = false;
  };

  const showKeyForm = credentialsQuery.isSuccess && (!connected || replacing);

  // Connecting and disconnecting fail through the same state, so the complaint renders
  // beside whichever of the two is on screen. The branches are mutually exclusive — a
  // connected provider that is not being replaced never shows the key form — so this reads
  // as one error line, always adjacent to the control that produced it.
  const actionError =
    error === null ? null : <ErrorLine>{describeProviderError(error, providerLabel)}</ErrorLine>;

  useEffect(() => {
    if (showKeyForm && claimKeyFieldFocus.current) {
      claimKeyFieldFocus.current = false;
      keyFieldRef.current?.focus();
    }
  }, [showKeyForm]);

  return (
    <fieldset className="flex flex-col gap-2" data-testid="loadout-provider-section">
      <legend className={LABEL_CLASS}>AI model provider</legend>

      {optionsQuery.isPending ? (
        <p className={CAPTION_CLASS}>Reading the provider roster…</p>
      ) : null}
      {optionsQuery.isError ? (
        <ErrorLine>
          The providers this deployment offers could not be loaded.
          <Button
            variant="ghost"
            size="sm"
            data-testid="provider-options-retry"
            onClick={() => void optionsQuery.refetch()}
          >
            Retry
          </Button>
        </ErrorLine>
      ) : null}

      <div className="flex flex-col gap-1.5" role="radiogroup" aria-label="AI model provider">
        {options.map((option) => {
          const selected = option.id === selection.providerId;
          const doctrine = providerDoctrine(option.id).doctrine;
          const optionConnected =
            credentialsQuery.data?.some(
              (status) => status.provider === option.id && status.configured,
            ) ?? false;
          return (
            <button
              key={option.id}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={disabled}
              onClick={() => {
                selectProvider(option.id, option.requiresCredential);
              }}
              data-testid={`provider-option-${option.id}`}
              className={cn(
                'flex flex-col gap-0.5 rounded-[var(--aegis-radius-md)] border px-3 py-2 text-left transition-colors',
                selected
                  ? 'border-[var(--aegis-accent-line)] bg-[var(--aegis-accent-soft)]'
                  : 'border-[var(--aegis-border-subtle)] hover:border-[var(--aegis-border-strong)]',
              )}
            >
              <span className="flex items-center gap-2">
                <span className="text-sm font-medium text-[var(--aegis-text-primary)]">
                  {option.label}
                </span>
                {option.requiresCredential && credentialsQuery.isSuccess ? (
                  <span
                    className={cn(
                      'rounded-full border px-1.5 py-px font-mono text-[9px] uppercase tracking-wide',
                      optionConnected
                        ? 'border-[var(--aegis-accent-line)] text-[var(--aegis-accent-strong)]'
                        : 'border-[var(--aegis-border-subtle)] text-[var(--aegis-text-faint)]',
                    )}
                  >
                    {optionConnected ? 'Connected' : 'Key needed'}
                  </span>
                ) : null}
              </span>
              <span className="text-xs leading-4 text-[var(--aegis-text-muted)]">{doctrine}</span>
            </button>
          );
        })}
      </div>

      {needsCredential ? (
        <div
          data-testid="provider-credential-panel"
          className="flex flex-col gap-2.5 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-3 py-2.5"
        >
          {credentialsQuery.isPending ? (
            <p className={CAPTION_CLASS}>Checking which providers you have connected…</p>
          ) : null}
          {credentialsQuery.isError ? (
            <ErrorLine>
              Your connected providers could not be loaded.
              <Button
                variant="ghost"
                size="sm"
                data-testid="provider-credentials-retry"
                onClick={() => void credentialsQuery.refetch()}
              >
                Retry
              </Button>
            </ErrorLine>
          ) : null}

          {connected && !replacing ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p
                  data-testid="provider-connected"
                  className="font-mono text-[11px] text-[var(--aegis-text-secondary)]"
                >
                  <span
                    aria-hidden="true"
                    className="mr-1.5 inline-block size-1.5 rounded-full bg-[var(--aegis-accent-cyan)] align-middle"
                  />
                  {credential.keyHint ? `Connected (…${credential.keyHint})` : 'Connected'}
                </p>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    data-testid="provider-replace-key"
                    disabled={disabled || pending}
                    onClick={() => {
                      clearError();
                      claimKeyFieldFocus.current = true;
                      setReplacing(true);
                    }}
                  >
                    Replace key
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    data-testid="provider-disconnect"
                    disabled={disabled || pending}
                    onClick={() => void handleDisconnect()}
                  >
                    Disconnect
                  </Button>
                </div>
              </div>
              {actionError}
            </>
          ) : null}

          {showKeyForm ? (
            <form
              className="flex flex-col gap-1.5"
              onSubmit={(event) => {
                event.preventDefault();
                void handleConnect();
              }}
            >
              <label htmlFor={keyFieldId} className={LABEL_CLASS}>
                {providerLabel} API key
              </label>
              <div className="flex items-center gap-2">
                <input
                  id={keyFieldId}
                  ref={keyFieldRef}
                  data-testid="provider-api-key"
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  value={apiKey}
                  disabled={disabled || pending}
                  aria-describedby={keyHelpId}
                  placeholder="Paste your key"
                  onChange={(event) => {
                    setApiKey(event.target.value);
                  }}
                  className={FIELD_CLASS}
                />
                <Button
                  type="submit"
                  size="sm"
                  variant="secondary"
                  data-testid="provider-connect"
                  disabled={disabled || pending || apiKey.trim().length === 0}
                >
                  {pending ? 'Verifying…' : 'Connect'}
                </Button>
                {replacing ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    data-testid="provider-replace-cancel"
                    disabled={pending}
                    onClick={() => {
                      setApiKey('');
                      setReplacing(false);
                      clearError();
                    }}
                  >
                    Cancel
                  </Button>
                ) : null}
              </div>
              <p id={keyHelpId} className={CAPTION_CLASS}>
                Verified against {providerLabel} now, then stored encrypted against your account.
                The console never shows it again.
              </p>
              {actionError}
            </form>
          ) : null}

          {connected ? (
            <div className="flex flex-col gap-1.5">
              <p className={LABEL_CLASS}>Model</p>
              {modelsQuery.isPending ? (
                <p className={CAPTION_CLASS}>Reading the {providerLabel} catalogue…</p>
              ) : null}
              {modelsQuery.isError ? (
                <ErrorLine>
                  {describeProviderError(modelsQuery.error, providerLabel)}
                  <Button
                    variant="ghost"
                    size="sm"
                    data-testid="provider-models-retry"
                    onClick={() => void modelsQuery.refetch()}
                  >
                    Retry
                  </Button>
                </ErrorLine>
              ) : null}
              {modelsQuery.isSuccess ? (
                <>
                  {/* OpenRouter lists hundreds; a local endpoint lists one. Offer the filter
                      only where scrolling would actually be the alternative. */}
                  {models.length > MODEL_FILTER_THRESHOLD ? (
                    <input
                      type="search"
                      data-testid="provider-model-filter"
                      aria-label={`Filter ${providerLabel} models`}
                      aria-controls={listboxId}
                      value={filter}
                      disabled={disabled}
                      placeholder={`Filter ${String(models.length)} models…`}
                      onChange={(event) => {
                        setFilter(event.target.value);
                      }}
                      className={FIELD_CLASS}
                    />
                  ) : null}
                  {filtered.length === 0 ? (
                    <p data-testid="provider-models-empty" className={CAPTION_CLASS}>
                      No model matches that filter.
                    </p>
                  ) : (
                    <ModelListbox
                      listboxId={listboxId}
                      models={filtered}
                      selectedId={selection.modelId}
                      disabled={disabled}
                      onSelect={(modelId) => {
                        onSelectionChange({ ...selection, modelId });
                      }}
                    />
                  )}
                </>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </fieldset>
  );
}

'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { NodeStatus } from '@aegis/contracts-ts';
import type { ButtonProps, NodeStatusValue } from '@aegis/ui';
import { Badge, Button, MetricTile, Panel } from '@aegis/ui';

import type { ThemePreference } from '@/features/shell/contracts/panel-preferences';
import { useTheme } from '@/features/shell/hooks/use-theme';

import {
  countTokens,
  readTokenValue,
  TOKEN_GROUPS,
  tokenReference,
  type DesignToken,
} from './token-catalogue';

const COPY_RESET_MS = 1600;

/**
 * Copy text to the clipboard and briefly remember which key was copied so the
 * UI can confirm it. Uses the async Clipboard API with a graceful no-op when it
 * is unavailable (older browsers, insecure contexts).
 */
function useCopy(): {
  copiedKey: string | null;
  copy: (key: string, value: string) => void;
} {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current != null) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const copy = useCallback((key: string, value: string) => {
    const finish = () => {
      setCopiedKey(key);
      if (timeoutRef.current != null) {
        window.clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = window.setTimeout(() => {
        setCopiedKey(null);
      }, COPY_RESET_MS);
    };
    // `navigator.clipboard` is typed as always present but is genuinely absent
    // in insecure contexts and some test environments, so treat it as optional.
    const clipboard = (navigator as { clipboard?: Clipboard }).clipboard;
    if (clipboard) {
      void clipboard.writeText(value).then(finish, finish);
    } else {
      finish();
    }
  }, []);

  return { copiedKey, copy };
}

/**
 * Track the concrete `data-theme` applied to the document root, re-reading on
 * every attribute mutation. Keyed off the DOM attribute (which `ThemeManager`
 * writes) rather than the resolved-theme React state so token re-reads happen
 * *after* the new theme is on the element and `getComputedStyle` reflects it —
 * a single observer feeds every swatch its cue to re-resolve.
 */
function useDataThemeKey(): string {
  const [themeKey, setThemeKey] = useState('');
  useEffect(() => {
    const root = document.documentElement;
    const read = () => root.getAttribute('data-theme') ?? 'dark';
    setThemeKey(read());
    const observer = new MutationObserver(() => {
      setThemeKey(read());
    });
    observer.observe(root, {
      attributes: true,
      attributeFilter: ['data-theme'],
    });
    return () => {
      observer.disconnect();
    };
  }, []);
  return themeKey;
}

const THEME_OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: 'system', label: 'System' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
];

/**
 * Live theme switcher for the token showcase. Consumes the shared shell theme
 * preference so flipping it here drives the same `data-theme` swap the rest of
 * the app uses, letting every swatch below update in place. Guarded against
 * hydration mismatch: until mounted it renders the SSR default (`system`)
 * active, matching the server output (see the rail ThemeToggle for the pattern).
 */
function ThemeSwitcher() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const activePreference: ThemePreference = mounted ? theme : 'system';
  const effectiveResolved = mounted ? resolvedTheme : 'dark';

  return (
    <div
      className="flex flex-wrap items-center gap-3 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-canvas)] px-3 py-2.5"
      data-testid="design-system-theme-switcher"
    >
      <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aegis-text-secondary)]">
        Theme
      </span>
      <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Preview theme">
        {THEME_OPTIONS.map((option) => (
          <Button
            key={option.value}
            type="button"
            size="sm"
            variant={activePreference === option.value ? 'secondary' : 'ghost'}
            role="radio"
            aria-checked={activePreference === option.value}
            data-testid={`theme-switch-${option.value}`}
            onClick={() => {
              setTheme(option.value);
            }}
          >
            {option.label}
          </Button>
        ))}
      </div>
      <span className="font-mono text-xs text-[var(--aegis-text-muted)]" aria-live="polite">
        Resolved: {effectiveResolved}
      </span>
    </div>
  );
}

function TokenSwatch({ token, themeKey }: { token: DesignToken; themeKey: string }) {
  // Values are resolved on the client so the inspector always reflects the
  // live stylesheet rather than a hardcoded copy that could drift. Re-reading on
  // `themeKey` keeps every swatch in sync when the theme is switched in place.
  const [value, setValue] = useState('');
  useEffect(() => {
    setValue(readTokenValue(token.name));
  }, [token.name, themeKey]);

  const { copiedKey, copy } = useCopy();
  const reference = tokenReference(token.name);
  const isCopied = copiedKey === token.name;

  const preview =
    token.kind === 'color' ? (
      <span
        aria-hidden="true"
        className="h-9 w-9 shrink-0 rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-strong)]"
        style={{ background: value || 'transparent' }}
      />
    ) : (
      <span
        aria-hidden="true"
        className="h-9 w-9 shrink-0 border border-[var(--aegis-border-strong)] bg-[var(--aegis-surface-raised)]"
        style={{ borderRadius: value || 0 }}
      />
    );

  return (
    <button
      type="button"
      data-testid={`token-swatch-${token.name}`}
      onClick={() => {
        copy(token.name, reference);
      }}
      className="flex items-center gap-3 rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-panel)] px-3 py-2 text-left transition-colors hover:border-[var(--aegis-border-strong)] hover:bg-[var(--aegis-surface-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--aegis-focus-ring)] motion-reduce:transition-none"
      aria-label={`Copy ${reference}${value ? `, value ${value}` : ''}`}
    >
      {preview}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm text-[var(--aegis-text-primary)]">
          {token.label}
        </span>
        <span className="block truncate font-mono text-xs text-[var(--aegis-text-secondary)]">
          {token.name}
        </span>
        <span className="block truncate font-mono text-xs text-[var(--aegis-text-muted)]">
          {value || '…'}
        </span>
      </span>
      <span
        className="shrink-0 font-mono text-xs uppercase tracking-wide text-[var(--aegis-accent-cyan)]"
        aria-hidden="true"
      >
        {isCopied ? 'Copied' : 'Copy'}
      </span>
    </button>
  );
}

export function TokenInspector() {
  const total = useMemo(() => countTokens(), []);
  const themeKey = useDataThemeKey();
  return (
    <Panel
      title="Design tokens"
      description={`${String(total)} live command-grid tokens · click any swatch to copy its var() reference`}
      data-testid="token-inspector"
    >
      <div className="mt-3 flex flex-col gap-6">
        <ThemeSwitcher />
        {TOKEN_GROUPS.map((group) => (
          <div key={group.id}>
            <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--aegis-text-secondary)]">
              {group.title}
            </h3>
            <p className="mb-2 text-xs text-[var(--aegis-text-muted)]">{group.description}</p>
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {group.tokens.map((token) => (
                <TokenSwatch key={token.name} token={token} themeKey={themeKey} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

const BUTTON_VARIANTS: NonNullable<ButtonProps['variant']>[] = [
  'default',
  'secondary',
  'outline',
  'ghost',
  'destructive',
];
const BUTTON_SIZES: NonNullable<ButtonProps['size']>[] = ['sm', 'md', 'lg'];
const STATUS_OPTIONS: { value: NodeStatusValue; label: string }[] = [
  { value: NodeStatus.NORMAL, label: 'Normal' },
  { value: NodeStatus.SUSPICIOUS, label: 'Suspicious' },
  { value: NodeStatus.UNDER_INVESTIGATION, label: 'Under investigation' },
  { value: NodeStatus.CONTAINED, label: 'Contained' },
  { value: NodeStatus.COMPROMISED, label: 'Compromised' },
];

function ChoiceRow<T extends string>({
  label,
  options,
  value,
  onChange,
  name,
}: {
  label: string;
  options: readonly { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  name: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aegis-text-secondary)]">
        {label}
      </span>
      <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label={label}>
        {options.map((option) => (
          <Button
            key={option.value}
            type="button"
            size="sm"
            variant={value === option.value ? 'secondary' : 'ghost'}
            role="radio"
            aria-checked={value === option.value}
            data-testid={`playground-${name}-${option.value}`}
            onClick={() => {
              onChange(option.value);
            }}
          >
            {option.label}
          </Button>
        ))}
      </div>
    </div>
  );
}

export function ComponentPlayground() {
  const [variant, setVariant] = useState<NonNullable<ButtonProps['variant']>>('default');
  const [size, setSize] = useState<NonNullable<ButtonProps['size']>>('md');
  const [status, setStatus] = useState<NodeStatusValue>(NodeStatus.SUSPICIOUS);
  const { copiedKey, copy } = useCopy();

  const snippet = `<Button variant="${variant}" size="${size}">Contain asset</Button>`;

  return (
    <Panel
      title="Component playground"
      description="Drive real @aegis/ui components with live props, then copy the JSX."
      data-testid="component-playground"
    >
      <div className="mt-3 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <ChoiceRow
            label="Variant"
            name="variant"
            options={BUTTON_VARIANTS.map((v) => ({ value: v, label: v }))}
            value={variant}
            onChange={setVariant}
          />
          <ChoiceRow
            label="Size"
            name="size"
            options={BUTTON_SIZES.map((s) => ({ value: s, label: s }))}
            value={size}
            onChange={setSize}
          />
          <ChoiceRow
            label="Badge status"
            name="status"
            options={STATUS_OPTIONS}
            value={status}
            onChange={setStatus}
          />
        </div>

        <div className="flex flex-col gap-4">
          <div
            className="flex min-h-24 flex-wrap items-center gap-3 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-canvas)] p-4"
            data-testid="playground-preview"
          >
            <Button variant={variant} size={size}>
              Contain asset
            </Button>
            <Badge nodeStatus={status} />
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aegis-text-secondary)]">
                JSX
              </span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                data-testid="playground-copy-snippet"
                onClick={() => {
                  copy('snippet', snippet);
                }}
              >
                {copiedKey === 'snippet' ? 'Copied' : 'Copy JSX'}
              </Button>
            </div>
            <pre className="overflow-x-auto rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-base)] p-3 font-mono text-xs text-[var(--aegis-text-primary)]">
              <code>{snippet}</code>
            </pre>
          </div>
        </div>
      </div>
    </Panel>
  );
}

const STATUS_SEMANTICS: { label: string; token: string; meaning: string }[] = [
  {
    label: 'Normal',
    token: '--aegis-status-normal',
    meaning: 'Baseline; no active signal.',
  },
  {
    label: 'Suspicious',
    token: '--aegis-status-suspicious',
    meaning: 'Anomaly raised, not yet triaged.',
  },
  {
    label: 'Under investigation',
    token: '--aegis-status-under-investigation',
    meaning: 'An agent or operator is actively working it.',
  },
  {
    label: 'Contained',
    token: '--aegis-status-contained',
    meaning: 'Approved containment applied; blast radius held.',
  },
  {
    label: 'Compromised',
    token: '--aegis-status-compromised',
    meaning: 'Confirmed adversary control of the asset.',
  },
];

const RISK_SEMANTICS: { label: string; token: string; meaning: string }[] = [
  { label: 'Low', token: '--aegis-risk-low', meaning: 'score < 0.35' },
  { label: 'Medium', token: '--aegis-risk-medium', meaning: '0.35 – 0.64' },
  { label: 'High', token: '--aegis-risk-high', meaning: '0.65 – 0.84' },
  {
    label: 'Critical',
    token: '--aegis-risk-critical',
    meaning: 'score ≥ 0.85',
  },
];

const KEYBOARD_SHORTCUTS: { keys: string; action: string; scope: string }[] = [
  { keys: 'Space', action: 'Play / pause playback', scope: 'Replay' },
  { keys: '← / →', action: 'Step cursor back / forward', scope: 'Replay' },
  {
    keys: 'Home / End',
    action: 'Jump to first / last sequence',
    scope: 'Replay',
  },
  { keys: '[ / ]', action: 'Decrease / increase speed', scope: 'Replay' },
  { keys: 'B', action: 'Cycle to next incident bookmark', scope: 'Replay' },
];

function LegendRow({ label, token, meaning }: { label: string; token: string; meaning: string }) {
  return (
    <li className="flex items-center gap-3 py-1.5">
      <span
        aria-hidden="true"
        className="h-3.5 w-3.5 shrink-0 rounded-full border border-[var(--aegis-border-strong)]"
        style={{ background: `var(${token})` }}
      />
      <span className="w-40 shrink-0 text-sm text-[var(--aegis-text-primary)]">{label}</span>
      <span className="text-xs text-[var(--aegis-text-secondary)]">{meaning}</span>
    </li>
  );
}

export function PlatformReference() {
  return (
    <Panel
      title="Platform reference"
      description="Fixed status and risk semantics, plus the replay keyboard map."
      data-testid="platform-reference"
    >
      <div className="mt-3 grid gap-6 lg:grid-cols-2">
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-[var(--aegis-text-secondary)]">
            Status semantics
          </h3>
          <ul>
            {STATUS_SEMANTICS.map((item) => (
              <LegendRow key={item.token} {...item} />
            ))}
          </ul>
        </div>

        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-[var(--aegis-text-secondary)]">
            Risk bands
          </h3>
          <ul>
            {RISK_SEMANTICS.map((item) => (
              <LegendRow key={item.token} {...item} />
            ))}
          </ul>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <MetricTile label="Example risk" value={0.72} riskBand="high" />
            <MetricTile label="Example risk" value={0.91} riskBand="critical" />
          </div>
        </div>

        <div className="lg:col-span-2">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-[var(--aegis-text-secondary)]">
            Keyboard shortcuts
          </h3>
          <table className="w-full border-collapse text-sm" data-testid="keyboard-reference">
            <caption className="sr-only">Replay keyboard shortcuts</caption>
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-[var(--aegis-text-muted)]">
                <th scope="col" className="py-1 pr-4 font-semibold">
                  Keys
                </th>
                <th scope="col" className="py-1 pr-4 font-semibold">
                  Action
                </th>
                <th scope="col" className="py-1 font-semibold">
                  Scope
                </th>
              </tr>
            </thead>
            <tbody>
              {KEYBOARD_SHORTCUTS.map((shortcut) => (
                <tr key={shortcut.keys} className="border-t border-[var(--aegis-border-subtle)]">
                  <td className="py-1.5 pr-4">
                    <kbd className="rounded border border-[var(--aegis-border-strong)] bg-[var(--aegis-surface-raised)] px-1.5 py-0.5 font-mono text-xs text-[var(--aegis-text-primary)]">
                      {shortcut.keys}
                    </kbd>
                  </td>
                  <td className="py-1.5 pr-4 text-[var(--aegis-text-primary)]">
                    {shortcut.action}
                  </td>
                  <td className="py-1.5 text-[var(--aegis-text-secondary)]">{shortcut.scope}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Panel>
  );
}

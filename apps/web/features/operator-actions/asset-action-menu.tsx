'use client';

import { useState } from 'react';

import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@aegis/ui';

import {
  COMMAND_CATALOGUE,
  commandMeta,
  requiresConfirmation,
  useSubmitOperatorAction,
  type ScenarioCommandTemplate,
} from '@/features/command-surface';

import { ActionConsequencesDialog } from './action-consequences-dialog';
import { ActionResultToast, type ActionResult } from './action-result-toast';

export interface AssetActionMenuProps {
  runId: string;
  assetId: string;
  assetLabel: string;
  /** Optional incident anchor; the service resolves a run-scoped incident when omitted. */
  incidentId?: string | null;
  /** Render as a compact icon-ish trigger (graph selection) vs a full-width button (drawer). */
  variant?: 'compact' | 'block';
  disabled?: boolean;
}

type PendingConfirm = { command: ScenarioCommandTemplate } | null;

/**
 * The operator's direct-action affordance for a single asset. Class 0/1 commands auto-execute
 * (the policy engine allows them) with a default justification; Class 2/3 commands open the
 * confirm-with-consequences dialog first. Every result — executed, needs-confirmation, or
 * blocked-by-policy — is surfaced honestly in a toast; the matching feed entry arrives via the
 * run's event stream. Actions route through the same policy pipeline as agent proposals.
 */
export function AssetActionMenu({
  runId,
  assetId,
  assetLabel,
  incidentId,
  variant = 'block',
  disabled,
}: AssetActionMenuProps) {
  const submit = useSubmitOperatorAction(runId);
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm>(null);
  const [reason, setReason] = useState('');
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [toast, setToast] = useState<ActionResult | null>(null);

  const runAction = (command: ScenarioCommandTemplate, confirmReason: string, confirm: boolean) => {
    const meta = commandMeta(command);
    submit.mutate(
      {
        command,
        targetAssetId: assetId,
        reason: confirmReason,
        confirm,
        incidentId: incidentId ?? null,
      },
      {
        onSuccess: (response) => {
          setToast({ commandLabel: meta.label, assetLabel, response });
          setPendingConfirm(null);
          setReason('');
          setDialogError(null);
        },
        onError: (error) => {
          // TError is ApiClientError (extends Error); surface its message honestly.
          const message = error.message || 'The action could not be submitted.';
          if (confirm) {
            // Keep the dialog open so the operator sees why and can retry.
            setDialogError(message);
          } else {
            setToast({
              commandLabel: meta.label,
              assetLabel,
              response: null,
              errorMessage: message,
            });
          }
        },
      },
    );
  };

  const onSelect = (command: ScenarioCommandTemplate) => {
    const meta = commandMeta(command);
    if (requiresConfirmation(meta.actionClass)) {
      setReason('');
      setDialogError(null);
      setPendingConfirm({ command });
      return;
    }
    // Class 0/1 auto-execute; carry a sensible default justification.
    runAction(command, `Operator ${meta.label.toLowerCase()} on ${assetLabel}.`, false);
  };

  const readOnly = COMMAND_CATALOGUE.filter(
    (c) => c.actionClass === 'class_0' || c.actionClass === 'class_1',
  );
  const operational = COMMAND_CATALOGUE.filter((c) => c.actionClass === 'class_2');
  const critical = COMMAND_CATALOGUE.filter((c) => c.actionClass === 'class_3');

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant={variant === 'compact' ? 'outline' : 'secondary'}
            size="sm"
            disabled={disabled || submit.isPending}
            data-testid="asset-action-trigger"
            className={variant === 'block' ? 'w-full justify-between' : undefined}
          >
            <span>Operator actions</span>
            <span aria-hidden="true" className="ml-2 text-[var(--aegis-text-muted)]">
              ▾
            </span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="min-w-[15rem]">
          <DropdownMenuLabel>Read &amp; monitor</DropdownMenuLabel>
          {readOnly.map((c) => (
            <DropdownMenuItem
              key={c.command}
              onSelect={() => {
                onSelect(c.command);
              }}
              data-testid={`action-item-${c.command}`}
            >
              <div className="flex flex-col">
                <span>{c.label}</span>
                <span className="text-[10px] text-[var(--aegis-text-muted)]">{c.summary}</span>
              </div>
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuLabel>Containment · needs confirm</DropdownMenuLabel>
          {operational.map((c) => (
            <DropdownMenuItem
              key={c.command}
              onSelect={() => {
                onSelect(c.command);
              }}
              data-testid={`action-item-${c.command}`}
            >
              <div className="flex flex-col">
                <span>{c.label}</span>
                <span className="text-[10px] text-[var(--aegis-text-muted)]">{c.summary}</span>
              </div>
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuLabel>Critical · needs confirm</DropdownMenuLabel>
          {critical.map((c) => (
            <DropdownMenuItem
              key={c.command}
              onSelect={() => {
                onSelect(c.command);
              }}
              data-testid={`action-item-${c.command}`}
            >
              <div className="flex flex-col">
                <span className="text-[var(--aegis-risk-high)]">{c.label}</span>
                <span className="text-[10px] text-[var(--aegis-text-muted)]">{c.summary}</span>
              </div>
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      {pendingConfirm ? (
        <ActionConsequencesDialog
          open
          command={pendingConfirm.command}
          assetLabel={assetLabel}
          assetId={assetId}
          reason={reason}
          onReasonChange={setReason}
          submitting={submit.isPending}
          errorMessage={dialogError}
          onConfirm={() => {
            runAction(pendingConfirm.command, reason.trim(), true);
          }}
          onCancel={() => {
            setPendingConfirm(null);
            setReason('');
            setDialogError(null);
          }}
        />
      ) : null}

      {toast ? (
        <ActionResultToast
          result={toast}
          onDismiss={() => {
            setToast(null);
          }}
        />
      ) : null}
    </>
  );
}

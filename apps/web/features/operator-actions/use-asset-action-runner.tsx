'use client';

import { useState, type ReactNode } from 'react';

import {
  commandMeta,
  requiresConfirmation,
  useSubmitOperatorAction,
  type ScenarioCommandTemplate,
} from '@/features/command-surface';

import { ActionConsequencesDialog } from './action-consequences-dialog';
import { ActionResultToast, type ActionResult } from './action-result-toast';

export interface AssetActionRunnerOptions {
  runId: string;
  assetId: string;
  assetLabel: string;
  /** Optional incident anchor; the service resolves a run-scoped incident when omitted. */
  incidentId?: string | null;
}

export interface AssetActionRunner {
  /** Invoke a command: Class 0/1 execute immediately, Class 2/3 open the confirm dialog. */
  select: (command: ScenarioCommandTemplate) => void;
  isPending: boolean;
  /** Confirm dialog and result toast. Render once inside the surface that owns the runner. */
  overlays: ReactNode;
}

type PendingConfirm = { command: ScenarioCommandTemplate } | null;

/**
 * Shared execution path behind every operator-action surface (graph context menu, stage
 * command bar, inspector menu). Class 0/1 commands auto-execute with a default
 * justification because the policy engine already allows them; Class 2/3 open the
 * confirm-with-consequences dialog first. Every outcome — executed, needs-confirmation, or
 * blocked-by-policy — is surfaced honestly in a toast; the matching feed entry arrives via
 * the run's event stream. Actions route through the same policy pipeline as agent proposals.
 */
export function useAssetActionRunner({
  runId,
  assetId,
  assetLabel,
  incidentId,
}: AssetActionRunnerOptions): AssetActionRunner {
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

  const select = (command: ScenarioCommandTemplate) => {
    const meta = commandMeta(command);
    if (requiresConfirmation(meta.actionClass)) {
      setReason('');
      setDialogError(null);
      setPendingConfirm({ command });
      return;
    }
    runAction(command, `Operator ${meta.label.toLowerCase()} on ${assetLabel}.`, false);
  };

  const overlays = (
    <>
      {pendingConfirm ? (
        <ActionConsequencesDialog
          open
          runId={runId}
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

  return { select, isPending: submit.isPending, overlays };
}

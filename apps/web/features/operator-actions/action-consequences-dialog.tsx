'use client';

import {
  Alert,
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@aegis/ui';

import {
  ACTION_CLASS_LABEL,
  commandMeta,
  type ScenarioCommandTemplate,
} from '@/features/command-surface';

import { BlastRadiusSummary } from './blast-radius-summary';
import { useBlastRadius } from './use-blast-radius';

export interface ActionConsequencesDialogProps {
  open: boolean;
  runId: string;
  command: ScenarioCommandTemplate;
  assetLabel: string;
  assetId: string;
  reason: string;
  onReasonChange: (reason: string) => void;
  submitting: boolean;
  errorMessage: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Confirm-with-consequences gate for a Class 2/3 operator action. The player is the incident
 * commander approving their own call, so the dialog names the action class, states
 * reversibility, and spells out the service impact before the single confirming click.
 */
export function ActionConsequencesDialog({
  open,
  runId,
  command,
  assetLabel,
  assetId,
  reason,
  onReasonChange,
  submitting,
  errorMessage,
  onConfirm,
  onCancel,
}: ActionConsequencesDialogProps) {
  const meta = commandMeta(command);
  const critical = meta.actionClass === 'class_3';
  const blastRadius = useBlastRadius(runId, command, assetId, { enabled: open });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          onCancel();
        }
      }}
    >
      <DialogContent data-testid="action-consequences-dialog">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <DialogTitle>{meta.label}</DialogTitle>
            <Badge variant="outline">{ACTION_CLASS_LABEL[meta.actionClass]}</Badge>
          </div>
          <DialogDescription>
            You are ordering this action as the incident commander. It takes effect on approval.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <div className="rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-3 py-2">
            <p className="font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
              Target
            </p>
            <p className="text-sm text-[var(--aegis-text-primary)]">{assetLabel}</p>
            <code className="font-mono text-[10px] text-[var(--aegis-text-secondary)]">
              {assetId}
            </code>
          </div>

          <Alert variant={critical ? 'error' : 'warning'} title="Consequences">
            <div className="flex flex-col gap-1.5">
              <p>{meta.consequence}</p>
              <p className="text-xs">
                Reversibility:{' '}
                <span className="font-semibold">
                  {meta.reversible ? 'reversible' : 'hard to undo'}
                </span>
                .
              </p>
            </div>
          </Alert>

          <BlastRadiusSummary
            preview={blastRadius.data}
            loading={blastRadius.isLoading}
            error={blastRadius.isError}
          />

          <div className="flex flex-col gap-1">
            <label
              htmlFor="action-reason"
              className="font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]"
            >
              Justification (audited)
            </label>
            <textarea
              id="action-reason"
              value={reason}
              rows={2}
              onChange={(e) => {
                onReasonChange(e.target.value);
              }}
              placeholder="Why this, why now — recorded on the action."
              className="w-full resize-none rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-base)] px-2.5 py-1.5 text-xs text-[var(--aegis-text-primary)] placeholder:text-[var(--aegis-text-muted)] focus:border-[var(--aegis-accent)] focus:outline-none"
            />
          </div>

          {errorMessage ? <Alert variant="error">{errorMessage}</Alert> : null}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onCancel} disabled={submitting}>
            Stand down
          </Button>
          <Button
            variant={critical ? 'destructive' : 'default'}
            onClick={onConfirm}
            disabled={submitting || reason.trim().length === 0}
            data-testid="action-confirm-execute"
          >
            {submitting ? 'Ordering…' : `Confirm ${meta.label.toLowerCase()}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

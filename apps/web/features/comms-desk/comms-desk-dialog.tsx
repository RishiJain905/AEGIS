'use client';

import { useEffect, useMemo, useState } from 'react';

import {
  Alert,
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  EmptyState,
} from '@aegis/ui';

import { useRequestSitrep, useSitrepHistory, type Sitrep } from './use-comms-desk';

const FAILURE_STATUSES = new Set(['failed', 'timed_out', 'cancelled']);

function formatStamp(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleTimeString();
}

/** Live elapsed seconds since `since` while `active`; resets when `since` changes. */
function useElapsedSeconds(active: boolean, since: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) {
      return;
    }
    setNow(Date.now());
    const id = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);
    return () => {
      window.clearInterval(id);
    };
  }, [active, since]);
  return Math.max(0, Math.floor((now - since) / 1000));
}

function SitrepView({ sitrep }: { sitrep: Sitrep }) {
  const [copied, setCopied] = useState(false);
  const hasBrief = sitrep.brief.trim().length > 0;
  const failed = FAILURE_STATUSES.has(sitrep.status) && !hasBrief;
  const compiling = !hasBrief && !failed;
  const startedMs = useMemo(() => new Date(sitrep.createdAt).getTime(), [sitrep.createdAt]);
  const elapsed = useElapsedSeconds(compiling, startedMs);

  const copy = () => {
    void navigator.clipboard.writeText(sitrep.brief).then(() => {
      setCopied(true);
      window.setTimeout(() => {
        setCopied(false);
      }, 1500);
    });
  };

  return (
    <div className="flex flex-col gap-2" data-testid="sitrep-view">
      <div className="flex items-center gap-2">
        <span className="font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
          {formatStamp(sitrep.createdAt)}
        </span>
        <Badge variant="outline" className="text-[9px]">
          {sitrep.status}
        </Badge>
        {sitrep.confidence !== null ? (
          <span className="font-mono text-[10px] text-[var(--aegis-text-muted)]">
            {Math.round(sitrep.confidence * 100)}% confidence
          </span>
        ) : null}
        {hasBrief ? (
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto"
            onClick={copy}
            data-testid="sitrep-copy"
          >
            {copied ? 'Copied' : 'Copy'}
          </Button>
        ) : null}
      </div>

      {failed ? (
        <Alert variant="error">
          The SITREP turn did not complete. Request another when the model is available.
        </Alert>
      ) : null}

      {compiling ? (
        <p className="text-xs text-[var(--aegis-text-muted)]" data-testid="sitrep-compiling">
          Compiling sitrep from live evidence… {elapsed}s elapsed. The local model is slow; this can
          take a minute.
        </p>
      ) : null}

      {hasBrief ? (
        <p
          className="whitespace-pre-wrap text-[0.8125rem] leading-6 text-[var(--aegis-text-primary)]"
          data-testid="sitrep-brief"
        >
          {sitrep.brief}
        </p>
      ) : null}

      {sitrep.evidenceIds.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5" data-testid="sitrep-evidence">
          <span className="font-mono text-[9px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
            Evidence
          </span>
          {sitrep.evidenceIds.map((id) => (
            <code
              key={id}
              className="rounded-[var(--aegis-radius-sm)] bg-[var(--aegis-surface-elevated)] px-1.5 py-0.5 font-mono text-[9px] text-[var(--aegis-text-secondary)]"
            >
              {id}
            </code>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export interface CommsDeskDialogProps {
  runId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * The SCRIBE comms desk: request a leadership-ready SITREP at any live moment and read the
 * grounded brief. Prior sitreps stay available as history (the SCRIBE session's task thread).
 */
export function CommsDeskDialog({ runId, open, onOpenChange }: CommsDeskDialogProps) {
  const { sitreps } = useSitrepHistory(runId);
  const request = useRequestSitrep(runId);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  const selected = sitreps.find((s) => s.taskId === selectedTaskId) ?? sitreps[0];
  const pendingElapsed = useElapsedSeconds(request.isPending, request.submittedAt || Date.now());

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="comms-desk-dialog">
        <DialogHeader>
          <DialogTitle>Comms desk · SITREP</DialogTitle>
          <DialogDescription>
            A leadership-ready brief compiled from the run&apos;s live evidence by SCRIBE.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <Button
              onClick={() => {
                request.mutate();
              }}
              disabled={request.isPending}
              data-testid="sitrep-request"
            >
              {request.isPending ? 'Compiling…' : 'Request SITREP'}
            </Button>
            {request.isPending ? (
              <span className="text-xs text-[var(--aegis-text-muted)]">
                compiling from live evidence… {pendingElapsed}s
              </span>
            ) : null}
          </div>

          {request.isError ? <Alert variant="error">{request.error.message}</Alert> : null}

          {selected ? (
            <SitrepView sitrep={selected} />
          ) : !request.isPending ? (
            <EmptyState
              title="No sitrep yet"
              description="Request a SITREP to compile the current situation into a shareable brief."
            />
          ) : null}

          {sitreps.length > 1 ? (
            <div className="flex flex-col gap-1 border-t border-[var(--aegis-border-subtle)] pt-2">
              <p className="font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
                History
              </p>
              <ul className="flex flex-col gap-1" data-testid="sitrep-history">
                {sitreps.map((sitrep) => (
                  <li key={sitrep.taskId}>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedTaskId(sitrep.taskId);
                      }}
                      aria-pressed={selected?.taskId === sitrep.taskId}
                      className="w-full rounded-[var(--aegis-radius-sm)] px-2 py-1 text-left text-xs text-[var(--aegis-text-secondary)] hover:bg-[var(--aegis-surface-raised)] aria-pressed:bg-[var(--aegis-surface-raised)]"
                    >
                      {formatStamp(sitrep.createdAt)} · {sitrep.status}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}

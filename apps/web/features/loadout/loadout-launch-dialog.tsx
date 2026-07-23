'use client';

import { useState } from 'react';

import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  cn,
} from '@aegis/ui';

import {
  DEFAULT_LOADOUT,
  ROE_DOCTRINE,
  RULES_OF_ENGAGEMENT,
  type RulesOfEngagement,
  type RunLoadout,
} from '@/features/command-surface';

function Toggle({
  id,
  label,
  description,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label
      htmlFor={id}
      className="flex cursor-pointer items-start gap-3 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-3 py-2.5"
    >
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => {
          onChange(e.target.checked);
        }}
        className="mt-0.5 size-4 accent-[var(--aegis-accent)]"
      />
      <span className="flex flex-col gap-0.5">
        <span className="text-sm font-medium text-[var(--aegis-text-primary)]">{label}</span>
        <span className="text-xs leading-4 text-[var(--aegis-text-muted)]">{description}</span>
      </span>
    </label>
  );
}

export interface LoadoutLaunchDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  scenarioName: string;
  launching: boolean;
  onLaunch: (loadout: RunLoadout) => void;
}

/**
 * Pre-launch loadout step: the second variety axis alongside the RNG seed. The operator
 * chooses their AI capabilities and rules of engagement before the run starts; the choice is
 * persisted on the run (POST /runs `loadout`). Defaults match the contract (bias guard on,
 * threat tempo on, RoE = investigate).
 */
export function LoadoutLaunchDialog({
  open,
  onOpenChange,
  scenarioName,
  launching,
  onLaunch,
}: LoadoutLaunchDialogProps) {
  const [biasGuard, setBiasGuard] = useState(DEFAULT_LOADOUT.biasGuard);
  const [threatTempo, setThreatTempo] = useState(DEFAULT_LOADOUT.threatTempo);
  const [roe, setRoe] = useState<RulesOfEngagement>(DEFAULT_LOADOUT.roe);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="loadout-launch-dialog">
        <DialogHeader>
          <DialogTitle>Configure loadout</DialogTitle>
          <DialogDescription>
            Play your cards for {scenarioName}. These capabilities are fixed for the run and,
            with the seed, make every engagement different.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <p className="font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
              Capabilities
            </p>
            <Toggle
              id="loadout-bias-guard"
              label="Bias guard"
              description="Agents flag evidence that contradicts your leading hypothesis."
              checked={biasGuard}
              onChange={setBiasGuard}
            />
            <Toggle
              id="loadout-threat-tempo"
              label="Threat tempo"
              description="An ambient pressure indicator derived from attacker progress. No position leakage."
              checked={threatTempo}
              onChange={setThreatTempo}
            />
          </div>

          <fieldset className="flex flex-col gap-2">
            <legend className="font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
              Rules of engagement
            </legend>
            <div className="flex flex-col gap-1.5" role="radiogroup" aria-label="Rules of engagement">
              {RULES_OF_ENGAGEMENT.map((candidate) => {
                const selected = candidate === roe;
                const doctrine = ROE_DOCTRINE[candidate];
                return (
                  <button
                    key={candidate}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => {
                      setRoe(candidate);
                    }}
                    data-testid={`roe-option-${candidate}`}
                    className={cn(
                      'flex flex-col gap-0.5 rounded-[var(--aegis-radius-md)] border px-3 py-2 text-left transition-colors',
                      selected
                        ? 'border-[var(--aegis-accent-line)] bg-[var(--aegis-accent-soft)]'
                        : 'border-[var(--aegis-border-subtle)] hover:border-[var(--aegis-border-strong)]',
                    )}
                  >
                    <span className="text-sm font-medium text-[var(--aegis-text-primary)]">
                      {doctrine.label}
                    </span>
                    <span className="text-xs leading-4 text-[var(--aegis-text-muted)]">
                      {doctrine.doctrine}
                    </span>
                  </button>
                );
              })}
            </div>
          </fieldset>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => { onOpenChange(false); }} disabled={launching}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              onLaunch({ schemaVersion: 1, biasGuard, threatTempo, roe });
            }}
            disabled={launching}
            data-testid="loadout-launch-confirm"
          >
            {launching ? 'Launching…' : 'Launch run'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

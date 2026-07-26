import { describe, expect, it } from 'vitest';

import { ASSET_KINDS, assetCommandCatalogue, type AssetKind } from './asset-command-catalogue';
import { COMMAND_CATALOGUE, commandMeta, SCENARIO_COMMANDS } from './contracts';

function commandsFor(assetType: string | null | undefined): string[] {
  return assetCommandCatalogue(assetType).map((entry) => entry.command);
}

describe('assetCommandCatalogue', () => {
  it('offers a different verb list per asset class rather than one list for everything', () => {
    // The whole point of the mapping: a datastore, an endpoint and a person do not share
    // a response toolkit.
    expect(commandsFor('database')).not.toEqual(commandsFor('device'));
    expect(commandsFor('user')).not.toEqual(commandsFor('service'));

    expect(commandsFor('database')).toEqual([
      'observe',
      'increase_monitoring',
      'restrict_access',
      'revoke_credentials',
      'isolate',
    ]);
    expect(commandsFor('device')).toEqual([
      'observe',
      'increase_monitoring',
      'isolate',
      'restrict_access',
      'restart_service',
    ]);
  });

  it('re-voices verbs for the target without inventing new ones', () => {
    const killProcess = assetCommandCatalogue('device').find(
      (entry) => entry.command === 'restart_service',
    );
    expect(killProcess?.label).toBe('Kill malicious process');

    const blockIps = assetCommandCatalogue('control').find(
      (entry) => entry.command === 'restrict_access',
    );
    expect(blockIps?.label).toBe('Block source addresses');
  });

  it('puts the account-killing framing on the command the simulation actually kills with', () => {
    // `access_restricted` is not one of the sim's IDENTITY_SEVERING_STATUSES — a narrowed
    // principal still authenticates and still grants its capabilities. Only
    // `revoke_credentials` severs it, so that is where "disable the account" belongs.
    const identity = assetCommandCatalogue('identity');
    const restrict = identity.find((entry) => entry.command === 'restrict_access');
    const revoke = identity.find((entry) => entry.command === 'revoke_credentials');

    expect(restrict?.label).toBe('Restrict entitlements');
    expect(restrict?.label).not.toMatch(/disable/i);
    expect(revoke?.label).toMatch(/disable account/i);
  });

  it('only ever offers commands the simulation and policy engine already understand', () => {
    const allowlist = new Set<string>(SCENARIO_COMMANDS);
    for (const kind of ASSET_KINDS) {
      for (const entry of assetCommandCatalogue(kind)) {
        expect(allowlist.has(entry.command)).toBe(true);
      }
    }
  });

  it('keeps every command’s policy class and reversibility exactly as the catalogue defines it', () => {
    for (const kind of ASSET_KINDS) {
      for (const entry of assetCommandCatalogue(kind)) {
        const canonical = commandMeta(entry.command);
        expect(entry.actionClass).toBe(canonical.actionClass);
        expect(entry.reversible).toBe(canonical.reversible);
      }
    }
  });

  it('never lists the same command twice for one asset class', () => {
    for (const kind of ASSET_KINDS) {
      const commands = commandsFor(kind);
      expect(new Set(commands).size).toBe(commands.length);
    }
  });

  it('leads every profile with the read tier so the quick-action buttons stay predictable', () => {
    for (const kind of ASSET_KINDS) {
      const [first, second, third] = assetCommandCatalogue(kind);
      expect(first?.actionClass).toBe('class_0');
      expect(second?.actionClass).toBe('class_1');
      // Third button is that class's headline containment move.
      expect(third?.actionClass).toBe('class_2');
    }
  });

  it('drops the critical tier entirely for asset classes that have no Class 3 move', () => {
    // You do not restart a person, and a datastore is not a deployment you roll back.
    for (const kind of ['database', 'user', 'identity'] satisfies AssetKind[]) {
      expect(assetCommandCatalogue(kind).some((entry) => entry.actionClass === 'class_3')).toBe(
        false,
      );
    }
    expect(assetCommandCatalogue('service').some((entry) => entry.actionClass === 'class_3')).toBe(
      true,
    );
  });

  it('falls back to the full catalogue for an unknown or unresolved asset class', () => {
    // Withholding a containment verb from an operator mid-incident is worse than offering
    // one policy will adjudicate anyway.
    expect(assetCommandCatalogue(null)).toBe(COMMAND_CATALOGUE);
    expect(assetCommandCatalogue(undefined)).toBe(COMMAND_CATALOGUE);
    expect(assetCommandCatalogue('nas-appliance')).toBe(COMMAND_CATALOGUE);
  });

  it('returns a referentially stable list so menus do not churn between renders', () => {
    expect(assetCommandCatalogue('database')).toBe(assetCommandCatalogue('database'));
  });
});

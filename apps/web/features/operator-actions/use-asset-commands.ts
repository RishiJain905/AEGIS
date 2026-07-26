'use client';

import { assetCommandCatalogue, type CommandMeta } from '@/features/command-surface';

/**
 * The command list offered for a given asset, in menu order (least to most destructive).
 *
 * Which verbs an asset gets is a property of its class, not of the console: you isolate a
 * host, you lock down and re-credential a database, you disable an account. The mapping is
 * authored in one place — {@link assetCommandCatalogue} — and this is the single seam every
 * operator-action surface reads it through: the command bar, the graph context menu, and the
 * inspector menu all render whatever list comes back, so the mapping changes in one module
 * and all three surfaces follow with no layout consequences.
 *
 * Deliberately a pure function of the asset's class rather than a lookup: every surface
 * already holds the node it is acting on, so making this fetch the graph would add a network
 * dependency (and a provider requirement) to what is a table read. `null` — an asset class
 * the caller could not determine — falls back to the full catalogue.
 */
export function useAssetCommands(assetType: string | null | undefined): readonly CommandMeta[] {
  return assetCommandCatalogue(assetType);
}

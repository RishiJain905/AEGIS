'use client';

import { COMMAND_CATALOGUE, type CommandMeta } from '@/features/command-surface';

/**
 * The command list offered for a given asset, in menu order (least to most destructive).
 *
 * Today every asset gets the full scenario catalogue. This is the single seam every
 * operator-action surface reads from — the command bar, the graph context menu, and the
 * inspector menu all render whatever list comes back — so making the verb list
 * asset-type-specific is a change to this function alone, with no layout consequences.
 */
export function useAssetCommands(_assetId: string): readonly CommandMeta[] {
  return COMMAND_CATALOGUE;
}

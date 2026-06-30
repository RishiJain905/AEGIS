import { z } from 'zod';

export const PANEL_PREFERENCES_SCHEMA_VERSION = 1;

export const panelRegionSchema = z.enum([
  'operationsRail',
  'inspector',
  'timeline',
  'visualization',
]);

export const panelRegionPreferenceSchema = z
  .object({
    docked: z.boolean(),
    collapsed: z.boolean(),
    width: z.number().int().min(200).max(640).nullable(),
  })
  .strict();

export const panelPreferencesSchema = z
  .object({
    schemaVersion: z.literal(PANEL_PREFERENCES_SCHEMA_VERSION),
    regions: z.record(panelRegionSchema, panelRegionPreferenceSchema),
  })
  .strict();

export type PanelRegion = z.infer<typeof panelRegionSchema>;
export type PanelRegionPreference = z.infer<typeof panelRegionPreferenceSchema>;
export type PanelPreferences = z.infer<typeof panelPreferencesSchema>;

export const defaultPanelPreferences: PanelPreferences = {
  schemaVersion: PANEL_PREFERENCES_SCHEMA_VERSION,
  regions: {
    operationsRail: { docked: true, collapsed: false, width: null },
    inspector: { docked: true, collapsed: false, width: 360 },
    timeline: { docked: true, collapsed: false, width: null },
    visualization: { docked: true, collapsed: false, width: null },
  },
};

export function parsePanelPreferences(data: unknown): PanelPreferences {
  const parsed = panelPreferencesSchema.safeParse(data);
  if (!parsed.success) {
    return defaultPanelPreferences;
  }
  return parsed.data;
}

import { z } from 'zod';

export const PANEL_PREFERENCES_SCHEMA_VERSION = 1;

/** localStorage key backing the persisted panel/theme preferences (zustand persist). */
export const PANEL_PREFERENCES_STORAGE_KEY = 'aegis-panel-preferences-v1';

/**
 * Operator theme preference. `system` follows the OS `prefers-color-scheme`
 * and is the default until the operator chooses explicitly; `light`/`dark`
 * are explicit choices. Resolves to a concrete `ResolvedTheme` at render time.
 */
export const themePreferenceSchema = z.enum(['system', 'light', 'dark']);
export type ThemePreference = z.infer<typeof themePreferenceSchema>;

/** The concrete theme actually applied to the document (`data-theme`). */
export type ResolvedTheme = 'light' | 'dark';

/** Default theme preference: follow the OS until the operator picks one. */
export const DEFAULT_THEME_PREFERENCE: ThemePreference = 'system';

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
    // Optional in persisted input for backward compatibility; defaults so
    // previously stored preferences (which predate the theme field) still parse.
    theme: themePreferenceSchema.default(DEFAULT_THEME_PREFERENCE),
    regions: z.record(panelRegionSchema, panelRegionPreferenceSchema),
  })
  .strict();

export type PanelRegion = z.infer<typeof panelRegionSchema>;
export type PanelRegionPreference = z.infer<typeof panelRegionPreferenceSchema>;
export type PanelPreferences = z.infer<typeof panelPreferencesSchema>;

export const defaultPanelPreferences: PanelPreferences = {
  schemaVersion: PANEL_PREFERENCES_SCHEMA_VERSION,
  theme: DEFAULT_THEME_PREFERENCE,
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

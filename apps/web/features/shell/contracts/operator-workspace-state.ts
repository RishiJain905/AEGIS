import { z } from 'zod';

export const OPERATOR_WORKSPACE_STATE_SCHEMA_VERSION = 1;

export const presentationModeSchema = z.enum(['live', 'historical', 'playback', 'incident']);

export const operatorWorkspaceStateSchema = z
  .object({
    schemaVersion: z.literal(OPERATOR_WORKSPACE_STATE_SCHEMA_VERSION),
    selectedEntityId: z.string().nullable(),
    selectedIncidentId: z.string().nullable(),
    commandPaletteOpen: z.boolean(),
    timelineCursorSequence: z.number().int().min(0).nullable(),
    presentationMode: presentationModeSchema,
    focusRestorationToken: z.string().nullable(),
  })
  .strict();

export type OperatorWorkspaceState = z.infer<typeof operatorWorkspaceStateSchema>;
export type PresentationMode = z.infer<typeof presentationModeSchema>;

export const defaultOperatorWorkspaceState: OperatorWorkspaceState = {
  schemaVersion: OPERATOR_WORKSPACE_STATE_SCHEMA_VERSION,
  selectedEntityId: null,
  selectedIncidentId: null,
  commandPaletteOpen: false,
  timelineCursorSequence: null,
  presentationMode: 'live',
  focusRestorationToken: null,
};

export function parseOperatorWorkspaceState(data: unknown): OperatorWorkspaceState {
  return operatorWorkspaceStateSchema.parse(data);
}

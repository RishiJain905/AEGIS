/**
 * Admin console response shapes.
 *
 * These mirror the read-only aggregation views served by /api/v1/admin/*. They are
 * admin-surface projections (not shared domain contracts), so they live with the
 * feature rather than in @aegis/contracts-ts.
 */

export interface AdminUser {
  userId: string;
  displayName: string;
  status: string;
  roles: string[];
  permissions: string[];
}

export interface AdminUsersResponse {
  schemaVersion: number;
  users: AdminUser[];
  total: number;
}

export interface AdminRolePermissions {
  role: string;
  permissions: string[];
}

export interface AdminActionClass {
  actionClass: string;
  label: string;
  approvalRequired: boolean;
  description: string;
}

export interface AdminCommand {
  command: string;
  actionClass: string;
  scenarioRestricted: boolean;
}

export interface AdminPolicyResponse {
  schemaVersion: number;
  roles: AdminRolePermissions[];
  permissions: string[];
  actionClasses: AdminActionClass[];
  commands: AdminCommand[];
  approverRoles: string[];
}

export interface AdminDependencyStatus {
  name: string;
  state?: string;
  status?: string;
  latencyMs?: number | null;
  required?: boolean;
  detail?: string | null;
}

/**
 * Model-provider probe result — a readiness axis of its own, deliberately kept
 * out of `status`/`dependencies`: AEGIS stays operable with the model down, so a
 * failing provider must never flip infrastructure readiness.
 *
 * `reportedModel` is what the provider server actually serves; `configuredModel`
 * is the env value. They drift, and the panel shows both when they disagree.
 */
export interface AdminModelProviderHealth {
  provider: string;
  state: 'ok' | 'failed' | 'skipped';
  baseUrl?: string | null;
  configuredModel?: string | null;
  reportedModels?: string[];
  reportedModel?: string | null;
  configuredModelServed?: boolean | null;
  latencyMs?: number | null;
  checkedAt?: string | null;
  message?: string | null;
}

export interface AdminSettingsHealth {
  status?: string;
  dependencies?: AdminDependencyStatus[];
  modelProvider?: AdminModelProviderHealth;
}

export interface AdminSettingsResponse {
  schemaVersion: number;
  environment: string;
  version: string;
  logLevel: string;
  provider: Record<string, unknown>;
  websocket: Record<string, unknown>;
  security: Record<string, unknown>;
  observability: Record<string, unknown>;
  auth: Record<string, unknown>;
  health: AdminSettingsHealth;
}

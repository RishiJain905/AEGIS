/**
 * Command-surface contract surface (operator console, direct actions, ops feed, loadout,
 * rules of engagement).
 *
 * The wire types now live in `@aegis/contracts-ts` (backend slice 1). This module re-exports
 * them under the short names the command-surface UI uses, and adds the UI-only helpers that
 * have no place in the shared contracts: the command catalogue (labels, reversibility,
 * consequence copy), the RoE doctrine descriptions, action-class labels, and the local
 * operator-hypothesis scratch type used until the hypotheses endpoint lands.
 */

import type {
  AutonomyInitiatorV1,
  ConsoleEventV1,
  ConsoleEventSearchRequestV1,
  ConsoleEventSearchResultV1,
  OperatorActionRequestV1,
  OperatorActionResponseV1,
  OperatorActionStatusV1,
  PolicyOutcomeV1,
  RulesOfEngagementV1,
  RunFeedEntryV1,
  RunFeedPageV1,
  RunLoadoutV1,
  ScenarioCommandTemplateV1,
} from '@aegis/contracts-ts';

// --- Wire types (re-exported from the shared contracts under the UI's short names) ---------

export type RulesOfEngagement = RulesOfEngagementV1;
export type RunLoadout = RunLoadoutV1;
export type ScenarioCommandTemplate = ScenarioCommandTemplateV1;
export type PolicyOutcome = PolicyOutcomeV1;
export type OperatorActionStatus = OperatorActionStatusV1;
export type OperatorActionRequest = OperatorActionRequestV1;
export type OperatorActionResponse = OperatorActionResponseV1;
export type RunFeedEntry = RunFeedEntryV1;
export type RunFeedPage = RunFeedPageV1;
export type ConsoleEvent = ConsoleEventV1;
export type ConsoleEventSearchRequest = ConsoleEventSearchRequestV1;
export type ConsoleEventSearchResult = ConsoleEventSearchResultV1;
/** Who originated an agent task (feed initiator badge). */
export type FeedInitiator = AutonomyInitiatorV1;

/**
 * Action class is not exported as a named type from the shared contracts (it is inlined in
 * the response schema). Re-declare the union here — the values are asserted against the
 * command catalogue below, so a drift in the contract surfaces as a type error.
 */
export type ActionClass = 'class_0' | 'class_1' | 'class_2' | 'class_3';

// --- Rules of engagement + loadout (UI helpers) -------------------------------------------

/** Iteration order for the RoE dial: least to most proactive. */
export const RULES_OF_ENGAGEMENT = ['observe', 'investigate', 'forward_deployed'] as const;

export const DEFAULT_LOADOUT: RunLoadout = {
  schemaVersion: 1,
  biasGuard: true,
  threatTempo: true,
  roe: 'investigate',
  // Null on both is "whatever this deployment runs by default" — which is what every run
  // launched before an operator could pin a provider already carries.
  providerId: null,
  modelId: null,
};

/**
 * The local endpoint's provider id: the one loadout option that needs no API key, and the
 * default every run falls back to. The server is the authority on which providers a
 * deployment offers (`GET /api/v1/providers/loadout-options`); this constant only names the
 * one the console assumes before that answer arrives.
 */
export const LOCAL_PROVIDER_ID = 'openai-compatible';

/**
 * One-line doctrine for each provider the launch dialog can offer, in the same voice as the
 * RoE dial. Labels come from the server (a deployment may rename one); these are the
 * fallback and the copy the server does not carry.
 */
export const PROVIDER_DOCTRINE: Record<string, { label: string; doctrine: string }> = {
  [LOCAL_PROVIDER_ID]: {
    label: 'Local model',
    doctrine: 'The model server this deployment already runs. Nothing leaves the machine.',
  },
  openai: {
    label: 'OpenAI',
    doctrine: 'Your own OpenAI account. Every agent in the run generates on the model you pick.',
  },
  openrouter: {
    label: 'OpenRouter',
    doctrine: 'One key, every vendor OpenRouter fronts. Hundreds of models — filter to yours.',
  },
  'ollama-cloud': {
    label: 'Ollama Cloud',
    doctrine: 'Your Ollama Cloud account, running the open-weight models it hosts.',
  },
};

/** Doctrine copy for a provider id, degrading to the raw id for one the console has no copy for. */
export function providerDoctrine(providerId: string): { label: string; doctrine: string } {
  return (
    PROVIDER_DOCTRINE[providerId] ?? {
      label: providerId,
      doctrine: 'Runs every agent in this run on your own subscription.',
    }
  );
}

/** One-line doctrine descriptions for the RoE dial, ordered from least to most proactive. */
export const ROE_DOCTRINE: Record<RulesOfEngagement, { label: string; doctrine: string }> = {
  observe: {
    label: 'Observe',
    doctrine: 'Agents watch and report. No investigation is opened without your word.',
  },
  investigate: {
    label: 'Investigate',
    doctrine: 'Agents autonomously triage new alerts and surface findings to the feed.',
  },
  forward_deployed: {
    label: 'Forward-deployed',
    doctrine: 'Agents proactively draft containment proposals for your approval.',
  },
};

// --- Operator direct actions (UI helpers) -------------------------------------------------

export const SCENARIO_COMMANDS = [
  'observe',
  'increase_monitoring',
  'isolate',
  'restrict_access',
  'revoke_credentials',
  'restart_service',
  'rollback_deployment',
] as const;

export interface CommandMeta {
  command: ScenarioCommandTemplate;
  label: string;
  actionClass: ActionClass;
  /** Whether the effect can be walked back without a fresh deployment/rebuild. */
  reversible: boolean;
  /** One-line "what this does" for the menu. */
  summary: string;
  /** Consequence copy shown in the confirm dialog for Class 2/3. */
  consequence: string;
}

/**
 * Command catalogue with the same command→class mapping the policy engine enforces
 * (`packages/policy/src/aegis_policy/commands.py`). Class 0/1 auto-execute; Class 2/3
 * require `confirm: true`. Kept in menu order (least to most destructive).
 */
export const COMMAND_CATALOGUE: readonly CommandMeta[] = [
  {
    command: 'observe',
    label: 'Observe',
    actionClass: 'class_0',
    reversible: true,
    summary: 'Pull the asset into focused watch. No state change.',
    consequence: 'Read-only. Marks the asset for closer monitoring.',
  },
  {
    command: 'increase_monitoring',
    label: 'Increase monitoring',
    actionClass: 'class_1',
    reversible: true,
    summary: 'Raise telemetry fidelity on this asset.',
    consequence: 'Low impact. Adds collection load but does not disrupt the asset.',
  },
  {
    command: 'isolate',
    label: 'Isolate',
    actionClass: 'class_2',
    reversible: true,
    summary: 'Cut the asset off from the network to contain spread.',
    consequence:
      'Severs the asset from the network. Dependent services lose it until you restore access.',
  },
  {
    command: 'restrict_access',
    label: 'Restrict access',
    actionClass: 'class_2',
    reversible: true,
    summary: 'Tighten access controls on the asset.',
    consequence: 'Legitimate sessions may be denied until access is widened again.',
  },
  {
    command: 'revoke_credentials',
    label: 'Revoke credentials',
    actionClass: 'class_2',
    reversible: true,
    summary: 'Invalidate the identity’s credentials.',
    consequence: 'Every session using these credentials drops. The principal must re-enrol.',
  },
  {
    command: 'restart_service',
    label: 'Restart service',
    actionClass: 'class_3',
    reversible: false,
    summary: 'Force a service restart.',
    consequence:
      'Critical. In-flight work on the service is dropped and downstream consumers see an outage window.',
  },
  {
    command: 'rollback_deployment',
    label: 'Rollback deployment',
    actionClass: 'class_3',
    reversible: false,
    summary: 'Roll the service back to its previous deployment.',
    consequence:
      'Critical and hard to undo. Replaces the running version; any state written since the last deploy may be lost.',
  },
] as const;

export function commandMeta(command: ScenarioCommandTemplate): CommandMeta {
  const found = COMMAND_CATALOGUE.find((entry) => entry.command === command);
  if (!found) {
    throw new Error(`Unknown scenario command: ${command}`);
  }
  return found;
}

/** Class 2/3 are the confirm-with-consequences tier (the operator is incident commander). */
export function requiresConfirmation(actionClass: ActionClass): boolean {
  return actionClass === 'class_2' || actionClass === 'class_3';
}

export const ACTION_CLASS_LABEL: Record<ActionClass, string> = {
  class_0: 'Class 0 · Read-only',
  class_1: 'Class 1 · Low impact',
  class_2: 'Class 2 · Operational',
  class_3: 'Class 3 · Critical',
};

// --- Ops feed (UI convenience) ------------------------------------------------------------

/** Coarse feed category emitted server-side (`console/service.py::_FEED_CATEGORIES`). */
export type FeedCategory =
  | 'agent'
  | 'operator_action'
  | 'roe'
  | 'proposal'
  | 'policy'
  | 'approval'
  | 'execution'
  | 'incident'
  | 'alert'
  | 'reveal'
  | 'directive';

// --- Operator hypotheses (interim; endpoint may not exist yet) ------------------------

export interface OperatorHypothesis {
  id: string;
  statement: string;
  assetIds: string[];
  confidence: number;
  createdAt: string;
  /** Local-only until the backend hypotheses endpoint lands; not persisted server-side. */
  local?: boolean;
}

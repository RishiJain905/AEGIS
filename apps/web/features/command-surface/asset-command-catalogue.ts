/**
 * Per-asset-type operator command catalogues.
 *
 * A responder does not have the same seven buttons for every asset. You isolate a host and
 * kill the process on it; you lock a database down and rotate its credentials; you disable an
 * account; you push a block-list through a control point. Offering the identical verb list on
 * a person, a Postgres cluster and a Kubernetes control plane is the tell that a console was
 * built around its API instead of around the job.
 *
 * What varies here is *availability and voice*, never semantics. Every entry is one of the
 * seven allowlisted {@link ScenarioCommandTemplate} identifiers the rest of the system already
 * speaks — the policy engine's class mapping
 * (`packages/policy/src/aegis_policy/commands.py::COMMAND_TO_ACTION_CLASS`), the world-state
 * footprint it drives (`COMMAND_STATUS_MAP` → `ContainmentStatus`), and the kill-chain
 * disruption the simulation derives from that status
 * (`packages/simulation-domain/.../disruption.py`). A profile may drop a verb or re-voice it
 * for the target; it can never invent one, re-class one, or change what executing it does.
 * That keeps one action vocabulary across UI, policy and simulation while the menu still reads
 * like what a responder could actually do to *that* asset class.
 *
 * The re-voicing is not cosmetic: the simulation's own disruption vocabulary already describes
 * these commands in asset-specific language ("killing a process / restarting a service resets
 * the in-progress technique's dwell", "blocking egress cuts exfiltration"). The labels below
 * simply say, per asset class, which of those framings applies.
 */

import type { GraphNodeV1 } from '@aegis/contracts-ts';

import {
  COMMAND_CATALOGUE,
  commandMeta,
  type CommandMeta,
  type ScenarioCommandTemplate,
} from './contracts';

/** The asset classes the graph contract distinguishes. */
export type AssetKind = GraphNodeV1['assetType'];

/**
 * One command as offered on one class of asset. `command` picks the canonical entry; the
 * optional fields re-voice it. Action class and reversibility are deliberately absent —
 * they come from the catalogue entry and are not a profile's to change.
 */
interface AssetCommandSpec {
  command: ScenarioCommandTemplate;
  label?: string;
  summary?: string;
  consequence?: string;
}

/**
 * Asset class → the commands a responder actually has against it, in menu order.
 *
 * Order matters twice: the menu groups by policy class, and the command bar promotes the
 * first three entries to one-click buttons. Each profile therefore opens with the two
 * read-tier verbs and puts that asset class's headline containment move third.
 */
const ASSET_COMMAND_PROFILES: Record<AssetKind, readonly AssetCommandSpec[]> = {
  /**
   * The workhorse type: APIs, brokers, gateways, pipelines, control planes. It is the only
   * class that carries the full toolkit, because a running service genuinely is the thing you
   * can pull off the network, re-credential, bounce, or roll back.
   */
  service: [
    { command: 'observe' },
    {
      command: 'increase_monitoring',
      label: 'Increase telemetry',
      summary: 'Raise log and trace fidelity on this service.',
    },
    {
      command: 'isolate',
      label: 'Isolate service',
      summary: 'Pull the service off the network to contain spread.',
      consequence:
        'Severs the service from the network. Every dependent service loses it until you restore access.',
    },
    {
      command: 'restrict_access',
      label: 'Restrict access',
      summary: 'Tighten the allowlist of callers this service will answer.',
      consequence:
        'Legitimate callers may be denied until the allowlist is widened, and data can no longer leave through this service.',
    },
    {
      command: 'revoke_credentials',
      label: 'Revoke service credentials',
      summary: 'Invalidate the API keys and service-account tokens this service issued or holds.',
      consequence:
        'Every session and integration using these credentials drops. The service must be re-enrolled before it works again.',
    },
    { command: 'restart_service' },
    { command: 'rollback_deployment', label: 'Roll back deployment' },
  ],

  /**
   * A datastore is not a deployment. Restarting it contains nothing and risks the data, and
   * there is no previous version to roll back to — so this profile has no Class 3 tier at all
   * and leads with the lockdown that actually stops collection and exfiltration.
   */
  database: [
    {
      command: 'observe',
      summary: 'Pull the database into focused watch. No state change.',
    },
    {
      command: 'increase_monitoring',
      label: 'Enable query auditing',
      summary: 'Log every statement and connection against this database.',
      consequence: 'Low impact. Adds write load for the audit trail; queries still serve.',
    },
    {
      command: 'restrict_access',
      label: 'Restrict access',
      summary: 'Cut the database down to its minimum authorised callers.',
      consequence:
        'Application tiers outside the allowlist start failing their queries, and no further data can be pulled out of this store.',
    },
    {
      command: 'revoke_credentials',
      label: 'Rotate database credentials',
      summary: 'Invalidate the database logins in play and force a rotation.',
      consequence:
        'Every open connection using these logins drops. Applications fail until their credentials are re-issued.',
    },
    {
      command: 'isolate',
      label: 'Quarantine database',
      summary: 'Take the database off the network entirely.',
      consequence:
        'Severs the store from every consumer. Anything that reads or writes it stops until you restore access.',
    },
  ],

  /**
   * Endpoints. The two verbs a responder reaches for are isolate-the-host and
   * kill-the-process — the latter is `restart_service`, whose world-state footprint
   * (`restarting`) is exactly the dwell reset the kill-chain engine reads as "the technique
   * running here was interrupted and must start over".
   */
  device: [
    {
      command: 'observe',
      summary: 'Pull the endpoint into focused watch. No state change.',
    },
    {
      command: 'increase_monitoring',
      label: 'Raise endpoint telemetry',
      summary: 'Turn up process, file and network collection on this endpoint.',
    },
    {
      command: 'isolate',
      label: 'Isolate host',
      summary: 'Contain the endpoint at the network layer, leaving it reachable for forensics.',
      consequence:
        'The host loses all network reachability. Whoever is using it is cut off mid-session.',
    },
    {
      command: 'restrict_access',
      label: 'Block egress',
      summary: 'Deny this endpoint outbound traffic while leaving internal access intact.',
      consequence:
        'Outbound connections fail, including the operator’s own remote tooling. Nothing can be staged out through this host.',
    },
    {
      command: 'restart_service',
      label: 'Kill malicious process',
      summary: 'Terminate the offending process tree and restart the affected service.',
      consequence:
        'Critical. The process is killed with whatever it held in memory, and anything the user had open on the host is lost.',
    },
  ],

  /**
   * A person. You cannot isolate, restart or roll back a human being — the only real levers
   * are the account behind them, so this profile has no Class 3 tier.
   */
  user: [
    {
      command: 'observe',
      label: 'Watch account activity',
      summary: 'Follow this person’s sign-ins and actions closely. No state change.',
    },
    {
      command: 'increase_monitoring',
      label: 'Raise authentication logging',
      summary: 'Capture full detail on every authentication this account makes.',
    },
    {
      command: 'restrict_access',
      label: 'Restrict account access',
      summary: 'Hold the account’s entitlements down to the bare minimum.',
      consequence:
        'The person loses access to most systems and cannot do their job until access is widened again. They can still sign in.',
    },
    {
      command: 'revoke_credentials',
      label: 'Revoke sessions & credentials',
      summary: 'Kill every live session and force a credential reset.',
      consequence:
        'The person is signed out everywhere and must re-enrol before working again. Anything running as them stops.',
    },
  ],

  /**
   * A non-human principal — service bot, workload identity, machine account. Same shape as a
   * person's account, different consequences: nothing here inconveniences a human, it breaks
   * whatever automation was running as the principal.
   *
   * Note which verb carries the account-killing framing. `access_restricted` is deliberately
   * *not* one of the simulation's `IDENTITY_SEVERING_STATUSES` — a narrowed principal can still
   * authenticate and still grants its capabilities — so "disable the account" belongs on
   * `revoke_credentials`, the command that actually kills them.
   */
  identity: [
    {
      command: 'observe',
      label: 'Watch principal activity',
      summary: 'Follow what this principal authenticates to. No state change.',
    },
    {
      command: 'increase_monitoring',
      label: 'Audit token issuance',
      summary: 'Record every token this principal is issued and where it is redeemed.',
    },
    {
      command: 'restrict_access',
      label: 'Restrict entitlements',
      summary: 'Cut the principal’s permissions back to the minimum it needs.',
      consequence:
        'Workflows running as this principal start failing on anything outside that minimum. The principal itself still authenticates.',
    },
    {
      command: 'revoke_credentials',
      label: 'Disable account & revoke credentials',
      summary: 'Kill the principal’s secrets and every token minted from them.',
      consequence:
        'All capabilities this principal granted die immediately. Automation depending on it must be re-credentialled before it runs again.',
    },
  ],

  /**
   * A security control / enforcement point. This is where a responder pushes a block-list —
   * enforcement happens *through* the control, so restricting it is what drops the attacker's
   * traffic. (Network gateways and brokers are typed `service` in the scenario data, not
   * `control`; a distinct gateway class would need a new `AssetType` in the graph contract.)
   */
  control: [
    {
      command: 'observe',
      summary: 'Pull the control point into focused watch. No state change.',
    },
    {
      command: 'increase_monitoring',
      label: 'Raise control-plane auditing',
      summary: 'Log every rule evaluation and administrative change on this control.',
    },
    {
      command: 'restrict_access',
      label: 'Block source addresses',
      summary: 'Push a deny rule for the hostile sources through this control point.',
      consequence:
        'Traffic matching the block list is dropped, legitimate sessions from those sources included. Nothing exfiltrates past this point.',
    },
    {
      command: 'isolate',
      // "Isolate the segment" is the responder's phrase, but the effect the simulation models
      // is on this control alone — the assets behind it are not themselves isolated — so the
      // consequence says what actually happens and lets the blast-radius preview quantify it.
      label: 'Isolate control point',
      summary: 'Cut the control itself off the network rather than tuning what it enforces.',
      consequence:
        'The control stops enforcing and anything that reached the estate through it loses that path, until you restore access.',
    },
    {
      command: 'restart_service',
      label: 'Restart control plane',
      summary: 'Force the control to reload and re-evaluate its rule set.',
      consequence:
        'Critical. Enforcement is briefly absent while the control reloads, and in-flight decisions are dropped.',
    },
  ],

  /**
   * A deployed model. It can be gated, taken offline, or rolled back to the previous version —
   * but it has no credentials of its own and "restart" is not how you deal with a poisoned or
   * suspect model.
   */
  ai_model: [
    {
      command: 'observe',
      summary: 'Pull the model into focused watch. No state change.',
    },
    {
      command: 'increase_monitoring',
      label: 'Log inference traffic',
      summary: 'Capture prompts, outputs and callers for every inference.',
    },
    {
      command: 'restrict_access',
      label: 'Restrict inference access',
      summary: 'Narrow the model to its minimum authorised callers.',
      consequence:
        'Callers outside the allowlist stop getting predictions, and no data leaves through the inference path.',
    },
    {
      command: 'isolate',
      label: 'Take model offline',
      summary: 'Withdraw the model from serving entirely.',
      consequence:
        'Every consumer of this model loses it and falls back to whatever it has, until you put the model back in service.',
    },
    {
      command: 'rollback_deployment',
      label: 'Roll back model version',
      summary: 'Restore the previously deployed version of the model.',
      consequence:
        'Critical and hard to undo. Serving reverts to the prior version; anything learned or written since that deploy may be lost.',
    },
  ],
};

/** Apply a profile's re-voicing on top of the canonical entry, preserving class + reversibility. */
function specialize(spec: AssetCommandSpec): CommandMeta {
  const base = commandMeta(spec.command);
  return {
    ...base,
    label: spec.label ?? base.label,
    summary: spec.summary ?? base.summary,
    consequence: spec.consequence ?? base.consequence,
  };
}

/** Every asset class that has a tailored profile (test + iteration helper). */
export const ASSET_KINDS = Object.keys(ASSET_COMMAND_PROFILES) as readonly AssetKind[];

// Resolved once at module load so every surface reading the same asset class gets a
// referentially stable list — a fresh array per render would churn memoized menu bodies.
// Keyed by plain string, because the lookup input is whatever the graph handed the surface.
const CATALOGUE_BY_ASSET_TYPE: ReadonlyMap<string, readonly CommandMeta[]> = new Map(
  ASSET_KINDS.map((kind) => [kind, Object.freeze(ASSET_COMMAND_PROFILES[kind].map(specialize))]),
);

/**
 * The commands offered on an asset of this class, in menu order.
 *
 * Unknown or not-yet-resolved types fall back to the full catalogue: better to offer a verb
 * the target may not deserve — policy still adjudicates it — than to silently withhold a
 * containment action from an operator mid-incident.
 */
export function assetCommandCatalogue(
  assetType: string | null | undefined,
): readonly CommandMeta[] {
  if (!assetType) {
    return COMMAND_CATALOGUE;
  }
  return CATALOGUE_BY_ASSET_TYPE.get(assetType) ?? COMMAND_CATALOGUE;
}

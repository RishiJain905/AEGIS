"""MITRE ATT&CK kill-chain shared vocabulary.

The attacker kill-chain engine (in the simulation-domain package) and the scenario
authoring layer (scenario-sdk) both need a single, stable set of ATT&CK *tactic*
identifiers plus the domain event types the engine emits as an attacker campaign
advances. Keeping them here — in the shared contracts package — means the scenario
manifest, the simulation runtime, and (later) the graph projection and scoring all
speak one vocabulary instead of independently redefining string constants.

Campaign *authoring* structures live in the scenario-sdk manifest schema; campaign
*runtime* progression is held in the simulation world state and (as of Phase 2)
serialized into ``WorldStateSnapshotV1`` so checkpoints round-trip it. The vocabulary
values below therefore appear in the cross-language checkpoint schema and are mirrored
as literal unions in ``@aegis/contracts`` — keep the two in step.
"""

from __future__ import annotations

from enum import StrEnum


class AttackTactic(StrEnum):
    """MITRE ATT&CK tactics an authored kill-chain technique may realize.

    Values are the canonical ATT&CK tactic shortnames so authored campaigns and any
    downstream ATT&CK mapping line up without translation.
    """

    INITIAL_ACCESS = "initial_access"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DEFENSE_EVASION = "defense_evasion"
    CREDENTIAL_ACCESS = "credential_access"
    DISCOVERY = "discovery"
    LATERAL_MOVEMENT = "lateral_movement"
    COLLECTION = "collection"
    COMMAND_AND_CONTROL = "command_and_control"
    EXFILTRATION = "exfiltration"
    IMPACT = "impact"


# Domain event types the kill-chain engine appends to the authoritative event stream.
# These are truth (fog-of-war disclosure is applied only when projecting to operators).
KILLCHAIN_CAMPAIGN_ACTIVATED = "sim.killchain.campaign_activated"
KILLCHAIN_TECHNIQUE_EXECUTED = "sim.killchain.technique_executed"
KILLCHAIN_REACTION_FIRED = "sim.killchain.reaction_fired"
KILLCHAIN_EXFILTRATION_COMPLETED = "sim.killchain.exfiltration_completed"
KILLCHAIN_CAMPAIGN_STALLED = "sim.killchain.campaign_stalled"
# Phase 2: a defender action severed something the attacker depended on, and the run's
# win/lose resolution.
KILLCHAIN_TECHNIQUE_DISRUPTED = "sim.killchain.technique_disrupted"
KILLCHAIN_CAMPAIGN_CONTAINED = "sim.killchain.campaign_contained"
RUN_OUTCOME_RESOLVED = "sim.run.outcome_resolved"


class CampaignStatus(StrEnum):
    """Lifecycle of an in-world attacker campaign.

    ``ACTIVE`` advances on the sim clock; ``STALLED`` fired a reaction rule whose
    scripted counter-move was unavailable; ``CONTAINED`` was cut off by defender action
    with no established fallback left; ``SUCCEEDED`` reached exfiltration. ``STALLED``
    and ``CONTAINED`` are both "attacker neutralized" for win resolution — they differ
    only in *how* the attacker ran out of road (authored reaction exhausted vs. every
    foothold/egress severed), which the after-action needs in order to explain the run.
    """

    ACTIVE = "active"
    STALLED = "stalled"
    CONTAINED = "contained"
    SUCCEEDED = "succeeded"


#: Campaign statuses that mean the attacker was stopped rather than stopping itself.
NEUTRALIZED_CAMPAIGN_STATUSES: frozenset[str] = frozenset(
    {CampaignStatus.STALLED.value, CampaignStatus.CONTAINED.value}
)


class ContainmentStatus(StrEnum):
    """Asset statuses a defender containment action drives an asset into.

    These are the *world-state* footprint of the response toolkit: the approval /
    operator-action pipeline turns an allowlisted scenario command into exactly one of
    these via ``effect.set_asset_status``. The kill-chain engine reads them back off
    world state (never off the command) so the same disruption is derived whether the
    action landed on the live in-memory runtime or was re-applied from the event stream
    during a cold runtime rebuild.

    ``aegis_policy.commands.COMMAND_STATUS_MAP`` is the authoritative command → status
    mapping; this enum must stay a superset of its values (asserted by a unit test).
    ``CONTAINED`` and ``QUARANTINED`` have no command today but are already part of the
    authored disruption vocabulary in scenario reaction rules.
    """

    OBSERVED = "observed"
    HEIGHTENED_MONITORING = "heightened_monitoring"
    ISOLATED = "isolated"
    ACCESS_RESTRICTED = "access_restricted"
    CREDENTIALS_REVOKED = "credentials_revoked"
    RESTARTING = "restarting"
    ROLLING_BACK = "rolling_back"
    CONTAINED = "contained"
    QUARANTINED = "quarantined"


class DisruptionEffect(StrEnum):
    """What a defender action took away from the attacker.

    Mirrors the design spec's action → kill-chain effect table: isolating a host severs
    the foothold it is standing on or the anchor it is reaching for, killing a process /
    restarting a service resets the in-progress technique's dwell, revoking credentials
    kills a stolen capability, and blocking egress cuts exfiltration even after a
    completed collection.
    """

    FOOTHOLD_SEVERED = "foothold_severed"
    ANCHOR_SEVERED = "anchor_severed"
    DWELL_RESET = "dwell_reset"
    CAPABILITY_REVOKED = "capability_revoked"
    EGRESS_BLOCKED = "egress_blocked"


class RunOutcome(StrEnum):
    """How the race against the attacker ended.

    ``WIN`` and ``COSTLY_WIN`` both mean every campaign was neutralized before exfil;
    they differ on proportionality — a costly win crippled enough of the org to cross the
    scenario's warning threshold. Over-containment past the *fail* threshold is its own
    loss even when the attacker was stopped, which is the blue-team judgement the design
    spec's locked decision 3 asks the game to teach.
    """

    WIN = "win"
    COSTLY_WIN = "costly_win"
    LOSS_EXFILTRATION = "loss_exfiltration"
    LOSS_OVER_CONTAINMENT = "loss_over_containment"
    UNRESOLVED = "unresolved"


class RunOutcomeReason(StrEnum):
    """The single condition that resolved the run, for the after-action explanation."""

    ALL_CAMPAIGNS_NEUTRALIZED = "all_campaigns_neutralized"
    EXFILTRATION_COMPLETED = "exfiltration_completed"
    OVER_CONTAINMENT_COST = "over_containment_cost"
    CRITICAL_SERVICES_CRIPPLED = "critical_services_crippled"
    HORIZON_ELAPSED = "horizon_elapsed"

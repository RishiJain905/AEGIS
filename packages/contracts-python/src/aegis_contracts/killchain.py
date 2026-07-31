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

from collections.abc import Iterable
from enum import StrEnum

from aegis_contracts.graph import NodeStatus


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


#: World-state asset status → the operator-facing :class:`~aegis_contracts.graph.NodeStatus`
#: it projects to.
#:
#: The world models an asset's *operational* state with the richer
#: :class:`ContainmentStatus` vocabulary (which control was applied), while the graph
#: contract exposes the *security posture* an operator reads off a node. Those are
#: deliberately different vocabularies at different altitudes, so every producer of a
#: ``GraphNodeV1`` has to translate. Projecting the raw world status straight through
#: makes ``GraphSnapshotV1`` validation reject the node (``'isolated'`` is not a
#: ``NodeStatus``) and strands the run: the snapshot write inside a STEP/RESUME command
#: fails, so the run can never advance past its first containment action again.
#:
#: The disruptive controls all read as ``CONTAINED`` — the operator has taken the asset
#: away from the attacker, and *how* is carried by the action feed and the event stream,
#: not by the node's posture. Observation-only controls read as ``UNDER_INVESTIGATION``:
#: they change what the defender is watching, never whether the asset is contained.
NODE_STATUS_BY_WORLD_STATUS: dict[str, str] = {
    ContainmentStatus.OBSERVED.value: "under_investigation",
    ContainmentStatus.HEIGHTENED_MONITORING.value: "under_investigation",
    ContainmentStatus.ISOLATED.value: "contained",
    ContainmentStatus.ACCESS_RESTRICTED.value: "contained",
    ContainmentStatus.CREDENTIALS_REVOKED.value: "contained",
    ContainmentStatus.RESTARTING.value: "contained",
    ContainmentStatus.ROLLING_BACK.value: "contained",
    ContainmentStatus.CONTAINED.value: "contained",
    ContainmentStatus.QUARANTINED.value: "contained",
}


#: Every value the defensive-control vocabulary can take.
CONTROL_STATUSES: frozenset[str] = frozenset(status.value for status in ContainmentStatus)

#: Controls that take the asset away from the attacker. An asset carrying one of these
#: reads as ``CONTAINED`` no matter what the attacker had done to it.
CONTAINING_CONTROL_STATUSES: frozenset[str] = frozenset(
    status
    for status, projected in NODE_STATUS_BY_WORLD_STATUS.items()
    if projected == NodeStatus.CONTAINED.value
)

#: Controls that only change what the defender is watching. These never mask the posture
#: underneath — an observed compromise is still a compromise.
OBSERVATION_CONTROL_STATUSES: frozenset[str] = frozenset(
    status
    for status, projected in NODE_STATUS_BY_WORLD_STATUS.items()
    if projected == NodeStatus.UNDER_INVESTIGATION.value
)


def is_control_status(status: str) -> bool:
    """Whether ``status`` names a defensive control rather than a security posture.

    The two vocabularies overlap on exactly one value, ``"contained"``, which is
    classified as a control: it is what a defender action (or an authored consequence
    event) *does* to an asset, and the disruption model reads it as foothold-severing.
    """
    return status in CONTROL_STATUSES


def project_node_status(world_status: str) -> NodeStatus:
    """Project a world-state asset status onto the operator-facing graph vocabulary.

    A status that is already a ``NodeStatus`` (the attacker-driven and baseline values —
    ``normal``/``suspicious``/``under_investigation``/``contained``/``compromised``)
    passes through unchanged. A containment status maps through
    :data:`NODE_STATUS_BY_WORLD_STATUS`.

    An unrecognized status projects to ``UNDER_INVESTIGATION`` rather than raising: an
    unknown status still means *something* moved this asset off baseline, and a projection
    that raises would wedge the whole run's snapshot write — the failure mode this
    function exists to prevent. Scenario-authored statuses are validated at authoring
    time, so this branch is a safety net, not an authoring escape hatch.
    """
    try:
        return NodeStatus(world_status)
    except ValueError:
        pass
    mapped = NODE_STATUS_BY_WORLD_STATUS.get(world_status)
    return NodeStatus(mapped) if mapped is not None else NodeStatus.UNDER_INVESTIGATION


def project_effective_status(posture: str, applied_controls: Iterable[str]) -> NodeStatus:
    """Compose a security posture and its applied controls into one operator-facing status.

    An asset carries two independent facts: what the attacker did to it (its *posture*)
    and what the defender did about it (its *applied controls*). ``GraphNodeV1`` has a
    single ``status`` field, so the two have to be composed at projection time — and the
    composition has to be lossless in the world state, or the response toolkit erases the
    intrusion it is responding to.

    Precedence, in order:

    1. Any containing control wins. Isolating a compromised host reads ``CONTAINED``: the
       operator's answer to the compromise is the salient fact, and the compromise itself
       is still on the asset for scoring, disruption, and the after-action to read.
    2. Otherwise a non-baseline posture wins. Observing a compromised host leaves it
       reading ``COMPROMISED`` — watching an asset is not a response to it, and hiding the
       compromise behind ``UNDER_INVESTIGATION`` is the defect this function exists to
       prevent.
    3. Otherwise an observation control on a baseline asset reads ``UNDER_INVESTIGATION``:
       nothing is known to be wrong, but the defender is looking.
    """
    controls = set(applied_controls)
    if controls & CONTAINING_CONTROL_STATUSES:
        return NodeStatus.CONTAINED
    posture_status = project_node_status(posture)
    if posture_status is not NodeStatus.NORMAL:
        return posture_status
    if controls & OBSERVATION_CONTROL_STATUSES:
        return NodeStatus.UNDER_INVESTIGATION
    return NodeStatus.NORMAL


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

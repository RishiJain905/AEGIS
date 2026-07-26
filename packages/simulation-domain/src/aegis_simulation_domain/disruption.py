"""Defender action -> attacker kill-chain disruption (pure functions).

This is the missing link the game-loop design calls out: response actions used to mutate
an asset's status and stop there, because there was no attacker for them to affect. Here
each containment status the response toolkit can put an asset into is given a concrete
effect on the attacker's chain, per the design spec's action -> effect table:

===========================  ================================================
Isolate / quarantine host    Severs the foothold the attacker stands on and any
                             anchor it reaches for; also cuts egress through it.
Restrict access / block IP   Cuts data out — exfiltration cannot complete through
                             that asset even after a finished collection.
Revoke credentials           Kills every capability the asset granted, blocking any
                             technique that consumes one.
Restart / rollback service   Halts the in-progress technique: its dwell resets and
                             the attacker has to start it over.
===========================  ================================================

**Everything here reads world state, never the action event.** That is deliberate: an
approved containment lands on the live in-memory runtime in one path and is re-applied
from the persisted event stream in another (a cold runtime rebuild replays
``sim.asset.status_changed`` directly). Deriving disruption from the resulting asset
statuses makes both paths produce identical attacker behaviour, which is what keeps the
"pure function of (seed, world state, action sequence)" determinism promise honest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aegis_contracts.killchain import AttackTactic, ContainmentStatus
from aegis_scenario_sdk.contracts.manifest import (
    KillChainCampaignV1,
    ProportionalityPolicyV1,
)

from aegis_simulation_domain.world_state import CampaignRuntimeState, WorldState

#: The attacker cannot operate from, or land on, an asset in one of these states.
FOOTHOLD_SEVERING_STATUSES: frozenset[str] = frozenset(
    {
        ContainmentStatus.ISOLATED.value,
        ContainmentStatus.QUARANTINED.value,
        ContainmentStatus.CONTAINED.value,
    }
)

#: Credentials/identity sourced from an asset in one of these states are dead.
IDENTITY_SEVERING_STATUSES: frozenset[str] = FOOTHOLD_SEVERING_STATUSES | frozenset(
    {ContainmentStatus.CREDENTIALS_REVOKED.value}
)

#: No data leaves through an asset in one of these states — the late-game exfil save.
EGRESS_SEVERING_STATUSES: frozenset[str] = FOOTHOLD_SEVERING_STATUSES | frozenset(
    {ContainmentStatus.ACCESS_RESTRICTED.value}
)

#: The technique running on this asset is interrupted and must start over.
EXECUTION_HALTING_STATUSES: frozenset[str] = frozenset(
    {
        ContainmentStatus.RESTARTING.value,
        ContainmentStatus.ROLLING_BACK.value,
    }
)

#: How much of an asset's business value each containment status takes away.
#: Read-only postures cost nothing; a full isolation costs the whole asset.
CONTAINMENT_IMPACT_WEIGHTS: dict[str, float] = {
    ContainmentStatus.ISOLATED.value: 1.0,
    ContainmentStatus.QUARANTINED.value: 1.0,
    ContainmentStatus.CONTAINED.value: 1.0,
    ContainmentStatus.ROLLING_BACK.value: 0.6,
    ContainmentStatus.RESTARTING.value: 0.5,
    ContainmentStatus.ACCESS_RESTRICTED.value: 0.35,
    ContainmentStatus.CREDENTIALS_REVOKED.value: 0.25,
    ContainmentStatus.HEIGHTENED_MONITORING.value: 0.0,
    ContainmentStatus.OBSERVED.value: 0.0,
}

# A critical asset still carries most of its weight when its criticality is low, so
# taking a low-value host offline is cheap but never free. Keeps the cost scale readable:
# a fully-isolated org reads 1.0 regardless of the criticality distribution.
_BASE_ASSET_WEIGHT = 0.25
_CRITICALITY_WEIGHT = 0.75


def asset_business_weight(criticality: float) -> float:
    """Business value of one asset, used to weight both cost and the org total."""
    return _BASE_ASSET_WEIGHT + _CRITICALITY_WEIGHT * criticality


def _status_of(world: WorldState, asset_id: str | None) -> str | None:
    if asset_id is None:
        return None
    asset = world.assets.get(asset_id)
    return None if asset is None else asset.status


@dataclass(frozen=True)
class DisruptionAssessment:
    """What defender action has taken away from one campaign, as of right now.

    Purely derived from current world state, so re-assessing after a counter-move (or
    after a runtime rebuild) always agrees with the first assessment given the same world.
    """

    foothold_severed: bool = False
    anchor_severed: bool = False
    egress_blocked: bool = False
    #: Capabilities the pending technique needs whose granting asset has been contained.
    blocking_capabilities: tuple[str, ...] = ()
    #: Every capability whose granting asset has been contained, blocking or not.
    revoked_capabilities: tuple[str, ...] = ()
    #: Assets currently mid-restart/rollback that are interrupting this campaign.
    halted_assets: tuple[tuple[str, str], ...] = ()
    #: Lowest-id established foothold still usable, if the attacker needs to fall back.
    fallback_foothold_id: str | None = None
    all_footholds_severed: bool = False

    @property
    def blocked(self) -> bool:
        """Whether the campaign has lost something the pending technique depends on.

        A blocked campaign needs to adapt or be contained; it will not simply resume.
        """
        return (
            self.foothold_severed
            or self.anchor_severed
            or self.egress_blocked
            or bool(self.blocking_capabilities)
        )

    @property
    def halts_execution(self) -> bool:
        """Whether the pending technique is merely interrupted rather than cut off.

        The attacker keeps everything it had; it just loses the progress it had made and
        has to run the technique again once the service settles.
        """
        return bool(self.halted_assets)


def assess_disruption(
    *,
    campaign: KillChainCampaignV1,
    state: CampaignRuntimeState,
    world: WorldState,
) -> DisruptionAssessment:
    """Assess how defender containment currently constrains ``campaign``."""
    index = state.next_technique_index
    technique = (
        campaign.techniques[index] if 0 <= index < len(campaign.techniques) else None
    )

    foothold_status = _status_of(world, state.current_foothold_id)
    foothold_severed = foothold_status in FOOTHOLD_SEVERING_STATUSES

    anchor_status = _status_of(world, state.pending_anchor_id)
    anchor_severed = anchor_status in FOOTHOLD_SEVERING_STATUSES

    # Exfiltration is the one tactic that also needs a path *out*: blocking egress on
    # either the staging foothold or the egress anchor stops it even mid-flight.
    egress_blocked = False
    if technique is not None and technique.tactic == AttackTactic.EXFILTRATION:
        egress_blocked = (
            anchor_status in EGRESS_SEVERING_STATUSES
            or foothold_status in EGRESS_SEVERING_STATUSES
        )

    revoked: list[str] = []
    for capability, source_asset_id in sorted(state.established_capabilities.items()):
        if capability in state.revoked_capabilities:
            revoked.append(capability)
            continue
        if _status_of(world, source_asset_id) in IDENTITY_SEVERING_STATUSES:
            revoked.append(capability)
    revoked_set = set(revoked)
    blocking = (
        tuple(c for c in technique.requires_capabilities if c in revoked_set)
        if technique is not None
        else ()
    )

    in_flight_assets = {
        asset_id
        for asset_id in (state.current_foothold_id, state.pending_anchor_id)
        if asset_id is not None
    }
    halted: list[tuple[str, str]] = []
    for asset_id in sorted(in_flight_assets):
        status = _status_of(world, asset_id)
        if status in EXECUTION_HALTING_STATUSES:
            halted.append((asset_id, str(status)))

    usable = sorted(
        asset_id
        for asset_id in state.established_footholds
        if asset_id != state.current_foothold_id
        and _status_of(world, asset_id) not in FOOTHOLD_SEVERING_STATUSES
    )
    all_severed = all(
        _status_of(world, asset_id) in FOOTHOLD_SEVERING_STATUSES
        for asset_id in state.established_footholds
    ) and bool(state.established_footholds)

    return DisruptionAssessment(
        foothold_severed=foothold_severed,
        anchor_severed=anchor_severed,
        egress_blocked=egress_blocked,
        blocking_capabilities=blocking,
        revoked_capabilities=tuple(revoked),
        halted_assets=tuple(halted),
        fallback_foothold_id=usable[0] if usable else None,
        all_footholds_severed=all_severed,
    )


@dataclass(frozen=True)
class BusinessDisruption:
    """Collateral cost of the defender's containment, as a fraction of the whole org."""

    cost: float = 0.0
    disrupted_asset_ids: tuple[str, ...] = ()
    #: Critical assets taken fully offline that the attacker never actually held.
    needless_critical_outages: tuple[str, ...] = ()
    contributions: dict[str, float] = field(default_factory=dict)


def compute_business_disruption(
    *,
    world: WorldState,
    attacker_held_asset_ids: frozenset[str],
    policy: ProportionalityPolicyV1,
) -> BusinessDisruption:
    """Score how much of the org the defender has needlessly taken out of service.

    Containment of an asset the attacker actually holds costs nothing here — cutting off
    a compromised host *is* the job, however critical the host, and a defender who
    isolates exactly the intrusion and nothing else should score a clean win. What this
    measures is the collateral: assets the attacker never reached that the defender took
    down anyway. That is the "isolating half the org to stop one intrusion" failure the
    design spec's proportionality decision exists to punish.

    A pure read of world state rather than a tally of past actions, so containment that
    has since been lifted stops counting — proportionality asks "how crippled is the org
    *now*", and the run-level peak is tracked separately for the actions that were only
    briefly catastrophic.
    """
    total_weight = sum(
        asset_business_weight(asset.criticality) for asset in world.assets.values()
    )
    if total_weight <= 0.0:
        return BusinessDisruption()

    disrupted: list[str] = []
    needless: list[str] = []
    contributions: dict[str, float] = {}
    cost = 0.0
    for asset_id in sorted(world.assets):
        asset = world.assets[asset_id]
        impact = CONTAINMENT_IMPACT_WEIGHTS.get(asset.status)
        if impact is None or impact <= 0.0:
            continue
        if asset_id in attacker_held_asset_ids:
            continue
        contribution = impact * asset_business_weight(asset.criticality) / total_weight
        cost += contribution
        disrupted.append(asset_id)
        contributions[asset_id] = contribution
        if impact >= 1.0 and asset.criticality >= policy.critical_asset_threshold:
            needless.append(asset_id)

    return BusinessDisruption(
        cost=min(cost, 1.0),
        disrupted_asset_ids=tuple(disrupted),
        needless_critical_outages=tuple(needless),
        contributions=contributions,
    )


def attacker_held_asset_ids(world: WorldState) -> frozenset[str]:
    """Every asset any campaign has ever established a foothold on."""
    held: set[str] = set()
    for state in world.campaigns.values():
        held.update(state.established_footholds)
        if state.current_foothold_id is not None:
            held.add(state.current_foothold_id)
    return frozenset(held)

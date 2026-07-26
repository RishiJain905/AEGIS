"""Deterministic kill-chain helpers (pure functions).

The runtime owns the event queue, clock, and sequence counter and therefore does the
*scheduling* and *event emission* for an attacker campaign. Everything here is a pure
function of world state (+ a seeded RNG stream, used only to break genuine ties): anchor
selection over the org's real relationship edges, and reaction-rule precondition
evaluation. Keeping these pure keeps the determinism story auditable — no wall clock,
no unseeded randomness, no hidden state.
"""

from __future__ import annotations

from aegis_scenario_sdk.contracts.manifest import (
    AnchorSelectorMode,
    AnchorSelectorV1,
    EdgeDirection,
    KillChainCampaignV1,
    ReactionCounterMoveType,
    ReactionCounterMoveV1,
    ReactionPreconditionType,
    ReactionPreconditionV1,
)

from aegis_simulation_domain.disruption import (
    FOOTHOLD_SEVERING_STATUSES,
    DisruptionAssessment,
)
from aegis_simulation_domain.random_streams import SeededRandomStreams
from aegis_simulation_domain.world_state import CampaignRuntimeState, WorldState


def find_campaign(
    campaigns: list[KillChainCampaignV1], campaign_id: str
) -> KillChainCampaignV1 | None:
    for campaign in campaigns:
        if campaign.id == campaign_id:
            return campaign
    return None


def resolve_anchor(
    selector: AnchorSelectorV1,
    *,
    world: WorldState,
    foothold_id: str | None,
    rng: SeededRandomStreams,
    stream_key: str,
) -> str | None:
    """Resolve the concrete anchor asset a selector points at, deterministically.

    ``by_id`` returns the named asset. ``by_asset_type`` returns the lowest-id asset of
    that type (a stable crown-jewel fallback). ``along_edge`` traverses real relationship
    edges of the given type from the current foothold (or ``from_asset_id``); with several
    candidates it draws from a dedicated seeded stream over the *sorted* candidate ids, so
    the choice is reproducible and never touches telemetry RNG streams.
    """
    if selector.mode == AnchorSelectorMode.BY_ID:
        return str(selector.asset_id) if selector.asset_id else None

    if selector.mode == AnchorSelectorMode.BY_ASSET_TYPE:
        if selector.asset_type is None:
            return None
        typed = sorted(
            asset.id
            for asset in world.assets.values()
            if asset.asset_type == selector.asset_type.value
        )
        return typed[0] if typed else None

    # ALONG_EDGE
    origin = str(selector.from_asset_id) if selector.from_asset_id else foothold_id
    if origin is None or selector.relationship_type is None:
        return None
    rel_type = selector.relationship_type.value
    candidates: list[str] = []
    for rel in world.relationships.values():
        if rel.relationship_type != rel_type:
            continue
        if selector.direction == EdgeDirection.OUTBOUND and rel.source_id == origin:
            candidates.append(rel.target_id)
        elif selector.direction == EdgeDirection.INBOUND and rel.target_id == origin:
            candidates.append(rel.source_id)
    if not candidates:
        return None
    candidates = sorted(set(candidates))
    if len(candidates) == 1:
        return candidates[0]
    index = rng.stream(stream_key).randrange(len(candidates))
    return candidates[index]


def precondition_met(
    precondition: ReactionPreconditionV1,
    *,
    world: WorldState,
    state: CampaignRuntimeState,
    assessment: DisruptionAssessment,
) -> bool:
    """Return whether a reaction precondition holds against current world state.

    ``assessment`` is the campaign's disruption reading for this step, so the
    action-driven preconditions agree exactly with the disruption the engine is about to
    resolve rather than re-deriving it from slightly different rules.
    """
    statuses = set(precondition.statuses)
    if precondition.type == ReactionPreconditionType.FOOTHOLD_ISOLATED:
        foothold = state.current_foothold_id
        if foothold is None:
            return False
        asset = world.assets.get(foothold)
        return asset is not None and asset.status in statuses
    if precondition.type == ReactionPreconditionType.ASSET_STATUS_IS:
        if precondition.asset_id is None:
            return False
        asset = world.assets.get(str(precondition.asset_id))
        return asset is not None and asset.status in statuses
    if precondition.type == ReactionPreconditionType.CAPABILITY_REVOKED:
        capability = precondition.capability
        if capability is None or capability not in state.established_capabilities:
            return False
        # Default to the asset that granted the capability: revoking *that* identity is
        # what kills it. An explicit assetId overrides, for capabilities an author wants
        # tied to a different control point.
        source_asset_id = (
            str(precondition.asset_id)
            if precondition.asset_id is not None
            else state.established_capabilities[capability]
        )
        asset = world.assets.get(source_asset_id)
        return asset is not None and asset.status in statuses
    if precondition.type == ReactionPreconditionType.PENDING_ANCHOR_DISRUPTED:
        return assessment.anchor_severed
    if precondition.type == ReactionPreconditionType.ALL_FOOTHOLDS_DISRUPTED:
        return assessment.all_footholds_severed
    return False


def counter_move_available(
    move: ReactionCounterMoveV1,
    *,
    campaign: KillChainCampaignV1,
    state: CampaignRuntimeState,
    world: WorldState,
) -> bool:
    """Whether the attacker still holds the capability a counter-move needs.

    A counter may only use something already established in-world. ``stall`` is always
    "available" (it is the give-up move), and so is ``go_quiet`` — going to ground needs
    nothing but patience. ``pivot_to_asset`` needs the target to be an established
    foothold the defender has not severed. ``activate_technique`` needs the referenced
    technique to exist and any ``requires_capability`` to be established *and not
    revoked* — a pre-planted backup credential is worthless once the defender has killed
    the identity that granted it.
    """
    if move.type in {ReactionCounterMoveType.STALL, ReactionCounterMoveType.GO_QUIET}:
        return True
    if move.type == ReactionCounterMoveType.PIVOT_TO_ASSET:
        target = str(move.asset_id) if move.asset_id else None
        if target is None or target not in state.established_footholds:
            return False
        asset = world.assets.get(target)
        return asset is not None and asset.status not in FOOTHOLD_SEVERING_STATUSES
    if move.type == ReactionCounterMoveType.ACTIVATE_TECHNIQUE:
        if move.technique_id is None:
            return False
        exists = any(t.id == move.technique_id for t in campaign.techniques)
        if not exists:
            return False
        if move.requires_capability is not None:
            return (
                move.requires_capability in state.established_capabilities
                and move.requires_capability not in state.revoked_capabilities
            )
        return True
    return False


def technique_index(campaign: KillChainCampaignV1, technique_id: str) -> int | None:
    for index, technique in enumerate(campaign.techniques):
        if technique.id == technique_id:
            return index
    return None

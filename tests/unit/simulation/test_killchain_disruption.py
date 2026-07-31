"""Phase 2 game loop: defender actions disrupt the kill chain, and the run resolves.

Four properties carry the phase: (1) each containment verb takes the right thing away
from the attacker, (2) a disrupted attacker adapts deterministically — falling back to an
asset it already owns, going quiet, or running out of road — (3) the run reaches a real
win/lose verdict that accounts for how much of the org the defender wrecked getting
there, and (4) all of that survives a checkpoint round-trip so save/resume and replay
reconstruct the same campaign.

Containment is applied the way the real pipeline applies it: by putting the asset into
the status ``aegis_policy.commands.COMMAND_STATUS_MAP`` maps the scenario command to.
That is exactly what ``effect.set_asset_status`` does on approval, so these tests
exercise the same world mutation an approved operator/BASTION action produces.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aegis_contracts.graph import AssetType, NodeStatus
from aegis_contracts.killchain import (
    AttackTactic,
    CampaignStatus,
    ContainmentStatus,
    DisruptionEffect,
    RunOutcome,
    RunOutcomeReason,
)
from aegis_contracts.proposals import ScenarioCommandTemplateV1
from aegis_policy.commands import COMMAND_STATUS_MAP
from aegis_scenario_sdk.contracts.manifest import (
    AnchorSelectorMode,
    AnchorSelectorV1,
    AssetTemplateV1,
    BehaviorPluginConfigV1,
    BranchOutcomeV1,
    KillChainCampaignV1,
    KillChainTechniqueV1,
    OutcomeBranchDefinitionV1,
    ProportionalityPolicyV1,
    ReactionCounterMoveType,
    ReactionCounterMoveV1,
    ReactionPreconditionType,
    ReactionPreconditionV1,
    ReactionRuleV1,
    RelationshipTemplateV1,
    ScenarioManifestV1,
    ScenarioMetadataV1,
    ScheduledEventDefinitionV1,
    ScoringCriterionV1,
    ScoringDefinitionV1,
    TechniqueSignalV1,
    ZoneDefinitionV1,
)
from aegis_simulation_domain import SimulationEngine
from aegis_simulation_domain.disruption import (
    assess_disruption,
    attacker_held_asset_ids,
    compute_business_disruption,
)
from aegis_simulation_domain.resolution import evaluate_run_outcome
from aegis_simulation_domain.runtime import SimulationRuntime
from aegis_simulation_domain.world_state import AssetState, CampaignRuntimeState, WorldState

SCENARIO_VERSION = "scenario-version:1.0.0"
CAMPAIGN_ID = "camp"
SEED = 7

# The four containment verbs this phase gives teeth to, as the statuses they land as.
ISOLATE = COMMAND_STATUS_MAP[ScenarioCommandTemplateV1.ISOLATE]
RESTRICT_ACCESS = COMMAND_STATUS_MAP[ScenarioCommandTemplateV1.RESTRICT_ACCESS]
REVOKE_CREDENTIALS = COMMAND_STATUS_MAP[ScenarioCommandTemplateV1.REVOKE_CREDENTIALS]
RESTART_SERVICE = COMMAND_STATUS_MAP[ScenarioCommandTemplateV1.RESTART_SERVICE]


# --------------------------------------------------------------------------- #
# Synthetic campaign: entry -> lateral -> collection -> exfil, with a backup   #
# foothold the attacker can fall back to.                                      #
# --------------------------------------------------------------------------- #


def _asset(asset_id: str, *, criticality: float = 0.4) -> AssetTemplateV1:
    return AssetTemplateV1(
        id=asset_id,
        assetType=AssetType.SERVICE,
        label=asset_id,
        zoneId="business-unit:z",
        criticality=criticality,
        initialRiskScore=0.1,
    )


def _campaign(
    *,
    reactions: list[ReactionRuleV1] | None = None,
    exfil_dwell: float = 30.0,
) -> KillChainCampaignV1:
    signal = TechniqueSignalV1(
        plugin=BehaviorPluginConfigV1(pluginId="telemetry.auth_attempt", config={})
    )
    return KillChainCampaignV1(
        id=CAMPAIGN_ID,
        name="Camp",
        boundBranchGroup="g",
        boundBranchId="branch-x",
        entryAnchor=AnchorSelectorV1(mode=AnchorSelectorMode.BY_ID, assetId="asset:entry"),
        techniques=[
            KillChainTechniqueV1(
                id="t-access",
                tactic=AttackTactic.INITIAL_ACCESS,
                attackTechniqueId="T1078",
                name="Valid Accounts",
                anchor=AnchorSelectorV1(mode=AnchorSelectorMode.BY_ID, assetId="asset:entry"),
                dwellSimSeconds=30,
                establishes=["stolen-cred"],
                signals=[signal],
            ),
            KillChainTechniqueV1(
                id="t-lateral",
                tactic=AttackTactic.LATERAL_MOVEMENT,
                attackTechniqueId="T1021",
                name="Remote Services",
                anchor=AnchorSelectorV1(mode=AnchorSelectorMode.BY_ID, assetId="asset:relay"),
                dwellSimSeconds=30,
                signals=[signal],
            ),
            KillChainTechniqueV1(
                id="t-collect",
                tactic=AttackTactic.COLLECTION,
                attackTechniqueId="T1213",
                name="Data from Repositories",
                anchor=AnchorSelectorV1(mode=AnchorSelectorMode.BY_ID, assetId="asset:crown"),
                dwellSimSeconds=30,
                movesFoothold=False,
                requiresCapabilities=["stolen-cred"],
                signals=[signal],
            ),
            KillChainTechniqueV1(
                id="t-exfil",
                tactic=AttackTactic.EXFILTRATION,
                attackTechniqueId="T1041",
                name="Exfiltration Over C2",
                anchor=AnchorSelectorV1(mode=AnchorSelectorMode.BY_ID, assetId="asset:egress"),
                dwellSimSeconds=exfil_dwell,
                movesFoothold=False,
                signals=[signal],
            ),
        ],
        reactions=reactions or [],
    )


def _manifest(
    *,
    reactions: list[ReactionRuleV1] | None = None,
    proportionality: ProportionalityPolicyV1 | None = None,
    exfil_dwell: float = 30.0,
) -> ScenarioManifestV1:
    return ScenarioManifestV1(
        schemaVersion=1,
        metadata=ScenarioMetadataV1(
            scenarioId="scenario:kc-disruption",
            name="Disruption",
            version="1.0.0",
            requiredPlatformVersion="0.0.0-phase10",
        ),
        zones=[ZoneDefinitionV1(id="business-unit:z", label="Z")],
        assets=[
            _asset("asset:entry"),
            _asset("asset:relay"),
            _asset("asset:crown", criticality=0.95),
            _asset("asset:egress"),
            _asset("asset:spare"),
            _asset("asset:bystander-a", criticality=0.95),
            _asset("asset:bystander-b", criticality=0.95),
        ],
        relationships=[
            RelationshipTemplateV1(
                id="edge:entry-relay",
                source="asset:entry",
                target="asset:relay",
                relationshipType="AUTHENTICATED_TO",
                confidence=1.0,
                riskContribution=0.1,
            )
        ],
        scheduledEvents=[
            ScheduledEventDefinitionV1(
                id="evt-select",
                simTime=datetime(2026, 1, 1, tzinfo=UTC),
                priority=0,
                tieBreaker=0,
                action=BehaviorPluginConfigV1(
                    pluginId="branch.seed_selector", config={"branchGroup": "g"}
                ),
            )
        ],
        branches=[
            OutcomeBranchDefinitionV1(
                id="branch-x",
                label="X",
                weight=1.0,
                branchGroup="g",
                triggerCondition="always",
                outcomes=[BranchOutcomeV1(targetRef=CAMPAIGN_ID)],
            )
        ],
        campaigns=[_campaign(reactions=reactions, exfil_dwell=exfil_dwell)],
        proportionality=proportionality or ProportionalityPolicyV1(),
        scoring=ScoringDefinitionV1(
            maxScore=100, criteria=[ScoringCriterionV1(id="c", label="C", weight=1.0)]
        ),
    )


def _runtime(manifest: ScenarioManifestV1 | None = None) -> SimulationRuntime:
    runtime = SimulationEngine.create_runtime(
        manifest=manifest or _manifest(), seed=SEED, scenario_version_id=SCENARIO_VERSION
    )
    runtime.start()
    return runtime


def _state(runtime: SimulationRuntime) -> CampaignRuntimeState:
    state = runtime.world.campaigns.get(CAMPAIGN_ID)
    assert state is not None, "campaign never activated"
    return state


def _advance_until(runtime: SimulationRuntime, predicate, *, limit: int = 400) -> None:
    """Step until ``predicate(runtime)`` holds, so tests never depend on step counts."""
    for _ in range(limit):
        if predicate(runtime):
            return
        if not runtime.step():
            break
    if not predicate(runtime):
        raise AssertionError("condition never reached")


def _completed(runtime: SimulationRuntime) -> list[str]:
    state = runtime.world.campaigns.get(CAMPAIGN_ID)
    return list(state.completed_technique_ids) if state else []


def _contain(runtime: SimulationRuntime, asset_id: str, status: str) -> None:
    """Apply a containment action exactly as ``effect.set_asset_status`` would."""
    runtime.world.assets[asset_id].apply_status(status)


def _events(runtime: SimulationRuntime, event_type: str) -> list[dict]:
    return [dict(e.payload) for e in runtime.events if e.type == event_type]


# --------------------------------------------------------------------------- #
# The status vocabulary the engine reads is the one the pipeline writes         #
# --------------------------------------------------------------------------- #


def test_containment_status_vocabulary_covers_every_command() -> None:
    # The engine derives disruption from asset status, so a command whose status the
    # engine has never heard of would silently do nothing to the attacker.
    known = {status.value for status in ContainmentStatus}
    assert set(COMMAND_STATUS_MAP.values()) <= known


# --------------------------------------------------------------------------- #
# Action -> disruption mapping (pure)                                          #
# --------------------------------------------------------------------------- #


def _bare_world(statuses: dict[str, str]) -> WorldState:
    world = WorldState()
    for asset_id, status in statuses.items():
        asset = AssetState(
            id=asset_id,
            asset_type="service",
            status=NodeStatus.NORMAL.value,
            risk_score=0.1,
            criticality=0.5,
            zone_id="z",
        )
        # Route through the world's own entry point so a control value lands in
        # ``applied_controls`` and a posture value lands in ``status``, exactly as the
        # effect plugin would place it.
        asset.apply_status(status)
        world.assets[asset_id] = asset
    return world


@pytest.mark.parametrize(
    ("status", "expect_foothold_severed", "expect_egress_blocked"),
    [
        (ISOLATE, True, True),
        (ContainmentStatus.QUARANTINED.value, True, True),
        # Blocking egress leaves the attacker on the box but stops data leaving.
        (RESTRICT_ACCESS, False, True),
        (REVOKE_CREDENTIALS, False, False),
        ("normal", False, False),
    ],
)
def test_containment_status_maps_to_the_right_disruption(
    status: str, expect_foothold_severed: bool, expect_egress_blocked: bool
) -> None:
    campaign = _campaign()
    world = _bare_world({"asset:egress": status, "asset:foot": status})
    state = CampaignRuntimeState(
        campaign_id=CAMPAIGN_ID,
        status=CampaignStatus.ACTIVE.value,
        current_foothold_id="asset:foot",
        pending_anchor_id="asset:egress",
        next_technique_index=3,  # the exfiltration technique
    )
    assessment = assess_disruption(campaign=campaign, state=state, world=world)
    assert assessment.foothold_severed is expect_foothold_severed
    assert assessment.egress_blocked is expect_egress_blocked


def test_revoking_credentials_kills_the_capability_it_granted() -> None:
    campaign = _campaign()
    world = _bare_world({"asset:vault": REVOKE_CREDENTIALS, "asset:crown": "normal"})
    state = CampaignRuntimeState(
        campaign_id=CAMPAIGN_ID,
        status=CampaignStatus.ACTIVE.value,
        current_foothold_id="asset:crown",
        pending_anchor_id="asset:crown",
        next_technique_index=2,  # collection, which requires stolen-cred
        established_capabilities={"stolen-cred": "asset:vault"},
    )
    assessment = assess_disruption(campaign=campaign, state=state, world=world)
    assert assessment.revoked_capabilities == ("stolen-cred",)
    assert assessment.blocking_capabilities == ("stolen-cred",)
    assert assessment.blocked is True


def test_fallback_prefers_a_foothold_the_defender_has_not_severed() -> None:
    campaign = _campaign()
    world = _bare_world(
        {"asset:a": ISOLATE, "asset:b": ISOLATE, "asset:c": "normal", "asset:foot": ISOLATE}
    )
    state = CampaignRuntimeState(
        campaign_id=CAMPAIGN_ID,
        status=CampaignStatus.ACTIVE.value,
        current_foothold_id="asset:foot",
        established_footholds={"asset:a", "asset:b", "asset:c", "asset:foot"},
    )
    assessment = assess_disruption(campaign=campaign, state=state, world=world)
    assert assessment.fallback_foothold_id == "asset:c"
    assert assessment.all_footholds_severed is False

    _bare = world.assets["asset:c"]
    _bare.apply_status(ISOLATE)
    assert assess_disruption(
        campaign=campaign, state=state, world=world
    ).all_footholds_severed is True


# --------------------------------------------------------------------------- #
# Business disruption + proportionality (pure)                                 #
# --------------------------------------------------------------------------- #


def test_disruption_cost_scales_with_criticality_and_ignores_read_only_actions() -> None:
    world = _bare_world({"asset:big": "normal", "asset:small": "normal"})
    world.assets["asset:big"].criticality = 1.0
    world.assets["asset:small"].criticality = 0.0
    policy = ProportionalityPolicyV1()

    baseline = compute_business_disruption(
        world=world, attacker_held_asset_ids=frozenset(), policy=policy
    )
    assert baseline.cost == 0.0

    world.assets["asset:small"].apply_status(
        COMMAND_STATUS_MAP[ScenarioCommandTemplateV1.INCREASE_MONITORING]
    )
    watched = compute_business_disruption(
        world=world, attacker_held_asset_ids=frozenset(), policy=policy
    )
    assert watched.cost == 0.0, "monitoring an asset costs the business nothing"

    world.assets["asset:small"].apply_status(ISOLATE)
    cheap = compute_business_disruption(
        world=world, attacker_held_asset_ids=frozenset(), policy=policy
    ).cost
    world.assets["asset:small"].lift_controls()
    world.assets["asset:big"].apply_status(ISOLATE)
    expensive = compute_business_disruption(
        world=world, attacker_held_asset_ids=frozenset(), policy=policy
    ).cost
    assert 0.0 < cheap < expensive < 1.0


def test_outage_on_an_asset_the_attacker_holds_is_never_needless() -> None:
    world = _bare_world({"asset:crown": ISOLATE, "asset:bystander": ISOLATE})
    world.assets["asset:crown"].criticality = 0.95
    world.assets["asset:bystander"].criticality = 0.95
    policy = ProportionalityPolicyV1()

    disruption = compute_business_disruption(
        world=world, attacker_held_asset_ids=frozenset({"asset:crown"}), policy=policy
    )
    assert disruption.needless_critical_outages == ("asset:bystander",)


# --------------------------------------------------------------------------- #
# Win/lose resolution (pure)                                                   #
# --------------------------------------------------------------------------- #


def _resolve(world: WorldState, *, horizon: bool = False, policy=None):
    policy = policy or ProportionalityPolicyV1()
    disruption = compute_business_disruption(
        world=world, attacker_held_asset_ids=attacker_held_asset_ids(world), policy=policy
    )
    return evaluate_run_outcome(
        world=world,
        disruption=disruption,
        peak_disruption_cost=disruption.cost,
        policy=policy,
        horizon_reached=horizon,
    )


def test_run_is_unresolved_while_the_attacker_is_still_moving() -> None:
    world = _bare_world({"asset:a": "normal"})
    world.campaigns[CAMPAIGN_ID] = CampaignRuntimeState(
        campaign_id=CAMPAIGN_ID, status=CampaignStatus.ACTIVE.value
    )
    assert _resolve(world) is None

    horizon = _resolve(world, horizon=True)
    assert horizon is not None
    assert horizon.outcome == RunOutcome.UNRESOLVED
    assert horizon.reason == RunOutcomeReason.HORIZON_ELAPSED


def test_exfiltration_loses_the_run_however_proportionate_the_response_was() -> None:
    world = _bare_world({"asset:a": "normal"})
    world.campaigns[CAMPAIGN_ID] = CampaignRuntimeState(
        campaign_id=CAMPAIGN_ID, status=CampaignStatus.SUCCEEDED.value, active=False
    )
    resolution = _resolve(world)
    assert resolution is not None
    assert resolution.outcome == RunOutcome.LOSS_EXFILTRATION
    assert resolution.succeeded_campaign_ids == (CAMPAIGN_ID,)


@pytest.mark.parametrize(
    "campaign_status", [CampaignStatus.CONTAINED.value, CampaignStatus.STALLED.value]
)
def test_neutralizing_every_campaign_wins(campaign_status: str) -> None:
    world = _bare_world({"asset:a": "normal"})
    world.campaigns[CAMPAIGN_ID] = CampaignRuntimeState(
        campaign_id=CAMPAIGN_ID, status=campaign_status, active=False
    )
    resolution = _resolve(world)
    assert resolution is not None
    assert resolution.outcome == RunOutcome.WIN
    assert resolution.neutralized_campaign_ids == (CAMPAIGN_ID,)


def test_a_win_bought_with_heavy_collateral_is_only_a_costly_win() -> None:
    world = _bare_world({f"asset:{i}": "normal" for i in range(10)})
    for i in range(3):
        world.assets[f"asset:{i}"].apply_status(ISOLATE)
    world.campaigns[CAMPAIGN_ID] = CampaignRuntimeState(
        campaign_id=CAMPAIGN_ID, status=CampaignStatus.CONTAINED.value, active=False
    )
    resolution = _resolve(world)
    assert resolution is not None
    assert resolution.outcome == RunOutcome.COSTLY_WIN
    assert resolution.disruption_cost >= ProportionalityPolicyV1().warn_threshold


def test_over_containment_loses_even_though_the_attacker_was_stopped() -> None:
    world = _bare_world({f"asset:{i}": "normal" for i in range(10)})
    for i in range(6):
        world.assets[f"asset:{i}"].apply_status(ISOLATE)
    world.campaigns[CAMPAIGN_ID] = CampaignRuntimeState(
        campaign_id=CAMPAIGN_ID, status=CampaignStatus.CONTAINED.value, active=False
    )
    resolution = _resolve(world)
    assert resolution is not None
    assert resolution.outcome == RunOutcome.LOSS_OVER_CONTAINMENT
    assert resolution.reason == RunOutcomeReason.OVER_CONTAINMENT_COST


def test_crippling_critical_services_the_attacker_never_touched_loses() -> None:
    world = _bare_world({f"asset:{i}": "normal" for i in range(40)})
    for asset in world.assets.values():
        asset.criticality = 0.1
    for i in range(2):
        world.assets[f"asset:{i}"].criticality = 0.95
        world.assets[f"asset:{i}"].apply_status(ISOLATE)
    world.campaigns[CAMPAIGN_ID] = CampaignRuntimeState(
        campaign_id=CAMPAIGN_ID, status=CampaignStatus.CONTAINED.value, active=False
    )
    resolution = _resolve(world)
    assert resolution is not None
    # Cost alone stays under the fail threshold; it is the two needless critical
    # outages that lose the run.
    assert resolution.disruption_cost < ProportionalityPolicyV1().fail_threshold
    assert resolution.outcome == RunOutcome.LOSS_OVER_CONTAINMENT
    assert resolution.reason == RunOutcomeReason.CRITICAL_SERVICES_CRIPPLED


# --------------------------------------------------------------------------- #
# Engine: the attacker actually reacts to what the defender does               #
# --------------------------------------------------------------------------- #


def test_isolating_the_foothold_forces_a_fallback_to_an_asset_already_owned() -> None:
    runtime = _runtime()
    _advance_until(runtime, lambda r: len(_completed(r)) >= 2)
    state = _state(runtime)
    foothold = state.current_foothold_id
    assert foothold == "asset:relay"

    _contain(runtime, foothold, ISOLATE)
    runtime.step()

    disrupted = _events(runtime, "sim.killchain.technique_disrupted")
    assert [d["effect"] for d in disrupted] == [DisruptionEffect.FOOTHOLD_SEVERED.value]
    # It re-establishes from the entry host it already owns — never from a fresh asset.
    assert state.current_foothold_id == "asset:entry"
    assert state.active is True
    assert state.status == CampaignStatus.ACTIVE.value


def test_isolating_every_foothold_contains_the_campaign_and_wins_the_run() -> None:
    runtime = _runtime()
    _advance_until(runtime, lambda r: len(_completed(r)) >= 2)
    state = _state(runtime)

    for asset_id in sorted(state.established_footholds):
        _contain(runtime, asset_id, ISOLATE)
    runtime.step()

    assert state.active is False
    assert state.status == CampaignStatus.CONTAINED.value
    contained = _events(runtime, "sim.killchain.campaign_contained")
    assert len(contained) == 1
    assert contained[0]["campaignId"] == CAMPAIGN_ID

    outcome = runtime.run_outcome
    assert outcome is not None
    assert outcome.outcome == RunOutcome.WIN.value
    assert outcome.neutralized_campaign_ids == [CAMPAIGN_ID]


def test_blocking_egress_stops_exfiltration_after_collection_already_completed() -> None:
    runtime = _runtime()
    _advance_until(runtime, lambda r: "t-collect" in _completed(r))
    state = _state(runtime)
    assert state.active is True, "collection completed, exfiltration still pending"

    # The late-game save: the data is staged, but it cannot leave.
    _contain(runtime, "asset:egress", RESTRICT_ACCESS)
    runtime.step()

    assert "t-exfil" not in _completed(runtime)
    assert state.status == CampaignStatus.CONTAINED.value
    disrupted = _events(runtime, "sim.killchain.technique_disrupted")
    assert disrupted[-1]["effect"] == DisruptionEffect.EGRESS_BLOCKED.value
    assert runtime.run_outcome is not None
    assert runtime.run_outcome.outcome == RunOutcome.WIN.value


def test_revoking_the_stolen_credential_blocks_the_technique_that_needs_it() -> None:
    runtime = _runtime()
    _advance_until(runtime, lambda r: len(_completed(r)) >= 2)
    state = _state(runtime)
    assert state.established_capabilities == {"stolen-cred": "asset:entry"}

    _contain(runtime, "asset:entry", REVOKE_CREDENTIALS)
    runtime.step()

    assert "stolen-cred" in state.revoked_capabilities
    revocations = [
        d
        for d in _events(runtime, "sim.killchain.technique_disrupted")
        if d["effect"] == DisruptionEffect.CAPABILITY_REVOKED.value
    ]
    assert revocations and revocations[0]["capability"] == "stolen-cred"
    # Collection needs that credential and has no way around it.
    assert state.status == CampaignStatus.CONTAINED.value
    assert "t-collect" not in _completed(runtime)


def test_restarting_a_service_resets_the_in_progress_technique_dwell() -> None:
    runtime = _runtime()
    _advance_until(runtime, lambda r: len(_completed(r)) >= 1)
    state = _state(runtime)
    before = state.schedule_seq

    _contain(runtime, "asset:relay", RESTART_SERVICE)
    runtime.step()

    resets = [
        d
        for d in _events(runtime, "sim.killchain.technique_disrupted")
        if d["effect"] == DisruptionEffect.DWELL_RESET.value
    ]
    assert len(resets) == 1
    assert resets[0]["disruptedByStatus"] == RESTART_SERVICE
    assert state.schedule_seq > before, "the pending advance was rescheduled"
    # A service that stays mid-restart must not re-reset every single step.
    runtime.step()
    runtime.step()
    assert len(
        [
            d
            for d in _events(runtime, "sim.killchain.technique_disrupted")
            if d["effect"] == DisruptionEffect.DWELL_RESET.value
        ]
    ) == 1


def test_going_quiet_slows_the_attacker_and_stops_its_telemetry() -> None:
    # The defender sweeps an unrelated host; the attacker notices the hunt and goes to
    # ground rather than losing anything, which is the adaptation the design spec asks
    # for alongside falling back and escalating.
    reactions = [
        ReactionRuleV1(
            id="r-quiet",
            precondition=ReactionPreconditionV1(
                type=ReactionPreconditionType.ASSET_STATUS_IS,
                assetId="asset:spare",
                statuses=[ISOLATE],
            ),
            counterMove=ReactionCounterMoveV1(
                type=ReactionCounterMoveType.GO_QUIET,
                dwellMultiplier=4.0,
                suppressSignals=True,
            ),
        )
    ]
    runtime = _runtime(_manifest(reactions=reactions))
    _advance_until(runtime, lambda r: len(_completed(r)) >= 1)
    state = _state(runtime)

    _contain(runtime, "asset:spare", ISOLATE)
    runtime.step()

    fired = _events(runtime, "sim.killchain.reaction_fired")
    assert [(f["reactionId"], f["outcome"]) for f in fired] == [("r-quiet", "went_quiet")]
    assert state.dwell_multiplier == 4.0
    assert state.signals_suppressed is True
    assert state.active is True, "going quiet costs the attacker nothing but time"

    # Slower: the live advance (the superseded one is still queued and will be skipped)
    # is a full 4x dwell out rather than 1x.
    live = [
        event
        for event in runtime.queue.to_list()
        if event.config.get("scheduleSeq") == state.schedule_seq
    ]
    assert len(live) == 1
    assert (live[0].sim_time - runtime.clock.sim_time).total_seconds() == 30 * 4

    # And silent: the remaining techniques land without emitting their telemetry beats.
    before = len(runtime.events)
    _advance_until(runtime, lambda r: len(_completed(r)) >= 2)
    assert [e for e in runtime.events[before:] if e.type.startswith("telemetry.")] == []


def test_letting_the_attacker_reach_exfiltration_loses_the_run() -> None:
    runtime = _runtime()
    _advance_until(runtime, lambda r: r.run_outcome is not None)
    outcome = runtime.run_outcome
    assert outcome is not None
    assert outcome.outcome == RunOutcome.LOSS_EXFILTRATION.value
    assert outcome.reason == RunOutcomeReason.EXFILTRATION_COMPLETED.value
    assert outcome.succeeded_campaign_ids == [CAMPAIGN_ID]


def test_over_containment_loses_the_run_mid_flight() -> None:
    runtime = _runtime()
    _advance_until(runtime, lambda r: len(_completed(r)) >= 1)

    # Panic response: take the whole org down to stop one intrusion.
    for asset_id in sorted(runtime.world.assets):
        _contain(runtime, asset_id, ISOLATE)
    runtime.step()

    outcome = runtime.run_outcome
    assert outcome is not None
    assert outcome.outcome == RunOutcome.LOSS_OVER_CONTAINMENT.value
    assert set(outcome.needless_critical_outages) >= {
        "asset:bystander-a",
        "asset:bystander-b",
    }


def test_the_verdict_is_recorded_once_and_never_revised() -> None:
    runtime = _runtime()
    _advance_until(runtime, lambda r: r.run_outcome is not None)
    first = runtime.run_outcome
    runtime.run_steps(50)
    assert runtime.run_outcome == first
    assert len(_events(runtime, "sim.run.outcome_resolved")) == 1


def test_a_campaign_free_scenario_never_resolves_an_outcome() -> None:
    manifest = _manifest()
    campaign_free = manifest.model_copy(update={"campaigns": []})
    runtime = SimulationEngine.create_runtime(
        manifest=campaign_free, seed=SEED, scenario_version_id=SCENARIO_VERSION
    )
    runtime.start()
    runtime.run_steps(200)
    runtime.stop()
    assert runtime.run_outcome is None
    assert _events(runtime, "sim.run.outcome_resolved") == []


# --------------------------------------------------------------------------- #
# Determinism: reactions are a pure function of the action sequence            #
# --------------------------------------------------------------------------- #


def test_the_same_action_sequence_reproduces_the_same_run() -> None:
    def play() -> str:
        runtime = _runtime()
        _advance_until(runtime, lambda r: len(_completed(r)) >= 2)
        _contain(runtime, "asset:relay", ISOLATE)
        runtime.run_steps(40)
        _contain(runtime, "asset:entry", REVOKE_CREDENTIALS)
        runtime.run_steps(40)
        return SimulationEngine.normalized_hash(
            runtime, scenario_version_id=SCENARIO_VERSION
        ).hash_value

    assert play() == play()


def test_a_different_action_sequence_produces_a_different_run() -> None:
    passive = _runtime()
    passive.run_steps(200)

    active = _runtime()
    _advance_until(active, lambda r: len(_completed(r)) >= 2)
    _contain(active, "asset:relay", ISOLATE)
    active.run_steps(200)

    assert (
        SimulationEngine.normalized_hash(passive, scenario_version_id=SCENARIO_VERSION).hash_value
        != SimulationEngine.normalized_hash(
            active, scenario_version_id=SCENARIO_VERSION
        ).hash_value
    )


# --------------------------------------------------------------------------- #
# Checkpoint round-trip of campaign state                                      #
# --------------------------------------------------------------------------- #


def test_checkpoint_round_trips_campaign_state_exactly() -> None:
    runtime = _runtime()
    _advance_until(runtime, lambda r: len(_completed(r)) >= 2)
    _contain(runtime, "asset:relay", ISOLATE)
    runtime.step()
    original = _state(runtime)

    checkpoint = runtime.snapshot_checkpoint()
    restored = SimulationEngine.create_runtime(
        manifest=_manifest(), seed=SEED, scenario_version_id=SCENARIO_VERSION
    )
    restored.restore(checkpoint)

    recovered = restored.world.campaigns[CAMPAIGN_ID]
    assert recovered == original


def test_a_restored_run_continues_the_campaign_identically() -> None:
    runtime = _runtime()
    _advance_until(runtime, lambda r: len(_completed(r)) >= 2)
    _contain(runtime, "asset:relay", ISOLATE)
    runtime.step()
    checkpoint = runtime.snapshot_checkpoint()

    restored = SimulationEngine.create_runtime(
        manifest=_manifest(), seed=SEED, scenario_version_id=SCENARIO_VERSION
    )
    restored.restore(checkpoint)

    live_tail = [e.type for e in runtime.run_steps(120)]
    restored_tail = [e.type for e in restored.run_steps(120)]
    assert live_tail == restored_tail
    assert restored.world.campaigns[CAMPAIGN_ID] == runtime.world.campaigns[CAMPAIGN_ID]
    assert restored.run_outcome == runtime.run_outcome


def test_a_pre_phase_two_checkpoint_still_restores() -> None:
    # Checkpoints written before campaign state existed carry no campaigns key; they must
    # still restore rather than failing a live run out of recovery.
    runtime = _runtime()
    runtime.run_steps(20)
    checkpoint = runtime.snapshot_checkpoint()
    legacy = checkpoint.world_state.model_dump(mode="json", by_alias=True)
    for key in ("campaigns", "peakDisruptionCost", "outcome"):
        legacy.pop(key, None)

    from aegis_contracts.simulation import WorldStateSnapshotV1

    reparsed = WorldStateSnapshotV1.model_validate(legacy)
    assert reparsed.campaigns == []
    assert reparsed.outcome is None
    assert reparsed.peak_disruption_cost == 0.0

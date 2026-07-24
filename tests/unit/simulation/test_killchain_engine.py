"""Phase 1 attacker MITRE ATT&CK kill-chain engine.

Covers the four load-bearing properties: (1) the campaign advances along the org's
REAL relationship edges with the authored ATT&CK techniques, (2) advancement is
seed-deterministic (identical normalized event hash across runs), (3) it activates only
for the seed that selects its bound root-cause branch, and (4) the reaction framework
fires deterministically against a world mutation (a stand-in for a future operator/AI
action) — pivoting to an established foothold, activating pre-planted persistence, or
stalling when no capability remains. Pure helpers (anchor resolution, precondition and
counter-move evaluation) are unit-tested directly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from aegis_contracts.graph import AssetType, RelationshipType
from aegis_contracts.killchain import AttackTactic
from aegis_scenario_sdk.contracts.manifest import (
    AnchorSelectorMode,
    AnchorSelectorV1,
    AssetTemplateV1,
    BehaviorPluginConfigV1,
    BranchOutcomeV1,
    EdgeDirection,
    GeneratorDefinitionV1,
    GeneratorScheduleV1,
    KillChainCampaignV1,
    KillChainTechniqueV1,
    OutcomeBranchDefinitionV1,
    ReactionCounterMoveType,
    ReactionCounterMoveV1,
    ReactionPreconditionType,
    ReactionPreconditionV1,
    ReactionRuleV1,
    ScenarioManifestV1,
    ScenarioMetadataV1,
    ScheduledEventDefinitionV1,
    ScoringCriterionV1,
    ScoringDefinitionV1,
    ZoneDefinitionV1,
)
from aegis_simulation_domain import SimulationEngine
from aegis_simulation_domain.killchain import (
    counter_move_available,
    precondition_met,
    resolve_anchor,
)
from aegis_simulation_domain.random_streams import SeededRandomStreams
from aegis_simulation_domain.runtime import SimulationRuntime
from aegis_simulation_domain.world_state import (
    AssetState,
    CampaignRuntimeState,
    RelationshipState,
    WorldState,
)

FIXTURE = Path("scenarios/operation-silent-relay")
SCENARIO_VERSION = "scenario-version:1.0.0"
CAMPAIGN_ID = "campaign-credentials-relay"
CREDENTIALS_SEED = 1000  # golden-seeds.yaml: selects branch-cause-credentials
MAINTENANCE_SEED = 1006  # selects branch-cause-maintenance (no campaign)


def _runtime(seed: int) -> SimulationRuntime:
    manifest = SimulationEngine.load_manifest(FIXTURE)
    return SimulationEngine.create_runtime(
        manifest=manifest, seed=seed, scenario_version_id=SCENARIO_VERSION
    )


def _killchain_types(runtime: SimulationRuntime) -> list[str]:
    return [e.type for e in runtime.events if e.type.startswith("sim.killchain.")]


# --------------------------------------------------------------------------- #
# Advancement over real edges + determinism                                   #
# --------------------------------------------------------------------------- #


def test_campaign_advances_through_attack_chain_over_real_edges() -> None:
    runtime = _runtime(CREDENTIALS_SEED)
    runtime.start()
    runtime.advance(runtime.configuration.initial_sim_time + timedelta(seconds=1200))

    executed = [
        (e.payload["attackTechniqueId"], e.payload["tactic"], e.payload["anchorAssetId"])
        for e in runtime.events
        if e.type == "sim.killchain.technique_executed"
    ]
    # initial access -> lateral (AUTHENTICATED_TO edge) -> escalation (ADMINISTERS edge)
    # -> collection (crown-jewel PII) -> exfiltration (egress gateway).
    assert executed == [
        ("T1078", "initial_access", "asset:identity-svc-logistics-bot"),
        ("T1021", "lateral_movement", "asset:svc-identity-broker"),
        ("T1078", "privilege_escalation", "asset:svc-service-account-vault"),
        ("T1213", "collection", "asset:database-customer-pii"),
        ("T1041", "exfiltration", "asset:svc-comms-gateway"),
    ]
    state = runtime.world.campaigns[CAMPAIGN_ID]
    assert state.status == "succeeded"
    assert state.active is False
    assert "backup-cred:svc-account-vault" in state.established_capabilities
    # The lateral/escalation anchors were reached by traversing real edges, so the
    # compromised assets are exactly the topology neighbours, not authored by id.
    assert "asset:svc-identity-broker" in state.established_footholds
    assert "asset:svc-service-account-vault" in state.established_footholds


def test_technique_compromises_its_anchor_asset() -> None:
    runtime = _runtime(CREDENTIALS_SEED)
    runtime.start()
    runtime.advance(runtime.configuration.initial_sim_time + timedelta(seconds=1200))
    assert runtime.world.assets["asset:database-customer-pii"].status == "compromised"
    assert runtime.world.assets["asset:svc-comms-gateway"].status == "compromised"


def test_advancement_is_seed_deterministic() -> None:
    def run() -> str:
        runtime = _runtime(CREDENTIALS_SEED)
        runtime.start()
        runtime.run_steps(300)
        return SimulationEngine.normalized_hash(
            runtime, scenario_version_id=SCENARIO_VERSION
        ).hash_value

    assert run() == run()


def test_campaign_only_activates_for_its_bound_branch() -> None:
    credentials = _runtime(CREDENTIALS_SEED)
    credentials.start()
    credentials.run_steps(300)
    assert "sim.killchain.campaign_activated" in _killchain_types(credentials)
    assert CAMPAIGN_ID in credentials.world.campaigns

    maintenance = _runtime(MAINTENANCE_SEED)
    maintenance.start()
    maintenance.run_steps(300)
    assert _killchain_types(maintenance) == []
    assert maintenance.world.campaigns == {}


# --------------------------------------------------------------------------- #
# Reaction framework (deterministic, action-driven)                           #
# --------------------------------------------------------------------------- #


def _advance_until_footholds(runtime: SimulationRuntime, count: int) -> CampaignRuntimeState:
    runtime.start()
    for _ in range(600):
        runtime.step()
        state = runtime.world.campaigns.get(CAMPAIGN_ID)
        if state is not None and len(state.established_footholds) >= count:
            return state
    raise AssertionError("campaign did not establish enough footholds")


def test_reaction_pivots_to_backup_foothold_when_isolated() -> None:
    runtime = _runtime(CREDENTIALS_SEED)
    state = _advance_until_footholds(runtime, 2)
    isolated = state.current_foothold_id
    assert isolated is not None

    # Simulate a future operator/AI isolate action on the attacker's current foothold.
    runtime.world.assets[isolated].status = "isolated"
    runtime.step()

    fired = [
        e for e in runtime.events if e.type == "sim.killchain.reaction_fired"
    ]
    assert [(e.payload["reactionId"], e.payload["outcome"]) for e in fired] == [
        ("reaction-foothold-isolated", "pivoted")
    ]
    assert state.current_foothold_id == "asset:identity-svc-logistics-bot"
    assert state.active is True


def test_reaction_fires_deterministically() -> None:
    def run() -> tuple[str | None, list[tuple[str, str]]]:
        runtime = _runtime(CREDENTIALS_SEED)
        state = _advance_until_footholds(runtime, 2)
        runtime.world.assets[state.current_foothold_id].status = "isolated"  # type: ignore[index]
        runtime.step()
        fired = [
            (e.payload["reactionId"], e.payload["outcome"])
            for e in runtime.events
            if e.type == "sim.killchain.reaction_fired"
        ]
        return state.current_foothold_id, fired

    assert run() == run()


def test_reaction_activates_planted_persistence_on_credential_revocation() -> None:
    runtime = _runtime(CREDENTIALS_SEED)
    # Advance until the vault-admin backup capability is established (after escalation).
    runtime.start()
    state = runtime.world.campaigns.get(CAMPAIGN_ID)
    for _ in range(600):
        runtime.step()
        state = runtime.world.campaigns.get(CAMPAIGN_ID)
        if state is not None and "backup-cred:svc-account-vault" in state.established_capabilities:
            break
    assert state is not None
    assert "backup-cred:svc-account-vault" in state.established_capabilities

    runtime.world.assets["asset:svc-service-account-vault"].status = "revoked"
    runtime.step()

    fired = [
        e.payload
        for e in runtime.events
        if e.type == "sim.killchain.reaction_fired"
        and e.payload["reactionId"] == "reaction-credential-revoked"
    ]
    assert fired and fired[0]["outcome"] == "activated_technique"
    # The pre-planted persistence technique (T1136) executes at the SSO broker.
    runtime.advance(runtime.clock.sim_time + timedelta(seconds=600))
    persisted = [
        e
        for e in runtime.events
        if e.type == "sim.killchain.technique_executed"
        and e.payload["techniqueId"] == "technique-persistence-account"
    ]
    assert persisted


# --------------------------------------------------------------------------- #
# Synthetic campaign — stall when the attacker runs out of counters           #
# --------------------------------------------------------------------------- #


def _stall_manifest() -> ScenarioManifestV1:
    def plugin() -> BehaviorPluginConfigV1:
        return BehaviorPluginConfigV1(pluginId="telemetry.auth_attempt", config={})

    return ScenarioManifestV1(
        schemaVersion=1,
        metadata=ScenarioMetadataV1(
            scenarioId="scenario:kc-stall",
            name="Stall",
            version="1.0.0",
            requiredPlatformVersion="0.0.0-phase10",
        ),
        zones=[ZoneDefinitionV1(id="business-unit:z", label="Z")],
        assets=[
            AssetTemplateV1(
                id="asset:a",
                assetType=AssetType.SERVICE,
                label="A",
                zoneId="business-unit:z",
                criticality=0.5,
                initialRiskScore=0.1,
            ),
            AssetTemplateV1(
                id="asset:b",
                assetType=AssetType.SERVICE,
                label="B",
                zoneId="business-unit:z",
                criticality=0.5,
                initialRiskScore=0.1,
            ),
        ],
        generators=[
            GeneratorDefinitionV1(
                id="gen-a",
                targetAssetId="asset:a",
                plugin=plugin(),
                schedule=GeneratorScheduleV1(intervalSimSeconds=10),
            )
        ],
        scheduledEvents=[
            ScheduledEventDefinitionV1(
                id="evt-select",
                simTime=datetime(2026, 1, 1, tzinfo=UTC),
                priority=0,
                tieBreaker=0,
                action=BehaviorPluginConfigV1(
                    pluginId="branch.seed_selector",
                    config={"branchGroup": "g"},
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
                outcomes=[BranchOutcomeV1(targetRef="camp")],
            )
        ],
        campaigns=[
            KillChainCampaignV1(
                id="camp",
                name="Camp",
                boundBranchGroup="g",
                boundBranchId="branch-x",
                entryAnchor=AnchorSelectorV1(
                    mode=AnchorSelectorMode.BY_ID, assetId="asset:a"
                ),
                techniques=[
                    KillChainTechniqueV1(
                        id="t1",
                        tactic=AttackTactic.INITIAL_ACCESS,
                        attackTechniqueId="T1078",
                        name="Valid Accounts",
                        anchor=AnchorSelectorV1(
                            mode=AnchorSelectorMode.BY_ID, assetId="asset:a"
                        ),
                        dwellSimSeconds=30,
                    ),
                    KillChainTechniqueV1(
                        id="t2",
                        tactic=AttackTactic.COLLECTION,
                        attackTechniqueId="T1213",
                        name="Collection",
                        anchor=AnchorSelectorV1(
                            mode=AnchorSelectorMode.BY_ID, assetId="asset:b"
                        ),
                        dwellSimSeconds=30,
                    ),
                ],
                reactions=[
                    ReactionRuleV1(
                        id="r-stall",
                        precondition=ReactionPreconditionV1(
                            type=ReactionPreconditionType.FOOTHOLD_ISOLATED
                        ),
                        # Pivot target is never compromised -> no counter available.
                        counterMove=ReactionCounterMoveV1(
                            type=ReactionCounterMoveType.PIVOT_TO_ASSET,
                            assetId="asset:b",
                        ),
                    )
                ],
            )
        ],
        scoring=ScoringDefinitionV1(
            maxScore=100,
            criteria=[ScoringCriterionV1(id="c", label="C", weight=1.0)],
        ),
    )


def test_reaction_stalls_when_no_counter_remains() -> None:
    runtime = SimulationEngine.create_runtime(
        manifest=_stall_manifest(),
        seed=7,
        scenario_version_id=SCENARIO_VERSION,
    )
    runtime.start()
    state = None
    for _ in range(200):
        runtime.step()
        state = runtime.world.campaigns.get("camp")
        if state is not None and state.current_foothold_id == "asset:a":
            break
    assert state is not None and state.current_foothold_id == "asset:a"

    runtime.world.assets["asset:a"].status = "isolated"
    runtime.step()

    assert state.active is False
    assert state.status == "stalled"
    assert "sim.killchain.campaign_stalled" in _killchain_types(runtime)


# --------------------------------------------------------------------------- #
# Pure helpers                                                                 #
# --------------------------------------------------------------------------- #


def _world_with_edges() -> WorldState:
    world = WorldState()
    for asset_id in ("asset:src", "asset:t1", "asset:t2", "asset:db"):
        world.assets[asset_id] = AssetState(
            id=asset_id,
            asset_type="database" if asset_id == "asset:db" else "service",
            status="normal",
            risk_score=0.1,
            criticality=0.5,
            zone_id="z",
        )
    world.relationships["e1"] = RelationshipState(
        id="e1",
        source_id="asset:src",
        target_id="asset:t1",
        relationship_type="COMMUNICATED_WITH",
        confidence=1.0,
        risk_contribution=0.1,
    )
    world.relationships["e2"] = RelationshipState(
        id="e2",
        source_id="asset:src",
        target_id="asset:t2",
        relationship_type="COMMUNICATED_WITH",
        confidence=1.0,
        risk_contribution=0.1,
    )
    return world


def test_resolve_anchor_by_id_and_asset_type() -> None:
    world = _world_with_edges()
    rng = SeededRandomStreams(1)
    by_id = AnchorSelectorV1(mode=AnchorSelectorMode.BY_ID, assetId="asset:t1")
    assert resolve_anchor(by_id, world=world, foothold_id=None, rng=rng, stream_key="k") == (
        "asset:t1"
    )
    by_type = AnchorSelectorV1(
        mode=AnchorSelectorMode.BY_ASSET_TYPE, assetType=AssetType.DATABASE
    )
    assert resolve_anchor(by_type, world=world, foothold_id=None, rng=rng, stream_key="k") == (
        "asset:db"
    )


def test_resolve_anchor_along_edge_is_deterministic() -> None:
    world = _world_with_edges()
    selector = AnchorSelectorV1(
        mode=AnchorSelectorMode.ALONG_EDGE,
        relationshipType=RelationshipType.COMMUNICATED_WITH,
        direction=EdgeDirection.OUTBOUND,
    )
    first = resolve_anchor(
        selector, world=world, foothold_id="asset:src", rng=SeededRandomStreams(3), stream_key="k"
    )
    second = resolve_anchor(
        selector, world=world, foothold_id="asset:src", rng=SeededRandomStreams(3), stream_key="k"
    )
    assert first == second
    assert first in {"asset:t1", "asset:t2"}


def test_counter_move_availability() -> None:
    campaign = _stall_manifest().campaigns[0]
    state = CampaignRuntimeState(campaign_id="camp", status="active")
    stall = ReactionCounterMoveV1(type=ReactionCounterMoveType.STALL)
    pivot = ReactionCounterMoveV1(
        type=ReactionCounterMoveType.PIVOT_TO_ASSET, assetId="asset:b"
    )
    assert counter_move_available(stall, campaign=campaign, state=state) is True
    assert counter_move_available(pivot, campaign=campaign, state=state) is False
    state.established_footholds.add("asset:b")
    assert counter_move_available(pivot, campaign=campaign, state=state) is True


def test_precondition_capability_revoked_requires_capability() -> None:
    world = _world_with_edges()
    world.assets["asset:t1"].status = "revoked"
    state = CampaignRuntimeState(campaign_id="camp", status="active")
    precondition = ReactionPreconditionV1(
        type=ReactionPreconditionType.CAPABILITY_REVOKED,
        assetId="asset:t1",
        statuses=["revoked"],
        capability="backup",
    )
    assert precondition_met(precondition, world=world, state=state) is False
    state.established_capabilities.add("backup")
    assert precondition_met(precondition, world=world, state=state) is True

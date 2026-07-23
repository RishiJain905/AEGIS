"""Platform-level fog-of-war disclosure model.

The simulation event log is always the whole truth (determinism, golden replays, and
post-run ground truth depend on it). *Disclosure* is a separate, purely derived question
asked only when building operator-facing projections: **may the operator see this asset's
true security state yet?**

An asset's true security state is DISCLOSED for a run iff:

* the asset is not governed by any hidden condition (ungoverned assets are always
  disclosed — nothing about them is being hidden), OR
* a governing hidden condition has ``revealed = true`` in the run's simulation state, OR
* any persisted alert/incident for the run references the asset (detection has surfaced
  it, so continuing to hide it would be dishonest to the operator).

Detection, ML, scoring, and the authoritative event stream always read full truth; this
module only feeds the transport that reaches the human. Everything here is a pure function
of a scenario manifest plus a small set of event-derived inputs, so it is deterministic and
identical across the snapshot path, the live WebSocket path, and replay.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from aegis_contracts import DomainEventEnvelopeV1, GraphSnapshotV1
from aegis_scenario_sdk.contracts.manifest import (
    GeneratorDefinitionV1,
    HiddenConditionDefinitionV1,
    ScenarioManifestV1,
    ScheduledEventDefinitionV1,
)

_REVEALED_EVENT = "sim.hidden_condition.revealed"
_ALERT_PREFIX = "alert."

# The status an undisclosed governed asset is shown as. Governed assets begin at their
# manifest ``initial_status`` (``normal`` in the shipped scenarios) and only an attacker
# ``effect.set_asset_status`` moves them while hidden, so the last *disclosed* status of a
# hidden-governed asset is always its baseline. We therefore redact to ``normal`` rather
# than tracking a per-asset last-disclosed history. Operator/agent containment changes are
# never governed by a hidden condition and so are never redacted.
REDACTED_STATUS = "normal"

_SET_STATUS_PLUGIN = "effect.set_asset_status"


@dataclass(frozen=True)
class GovernedAsset:
    """Static (manifest-derived) fog metadata for one attacker-governed asset."""

    asset_id: str
    condition_ids: frozenset[str]
    baseline_risk: float
    baseline_status: str


def build_governing_map(manifest: ScenarioManifestV1) -> dict[str, GovernedAsset]:
    """Map ``asset_id -> GovernedAsset`` for every asset an attacker effect can hide.

    An asset is *governed* when a hidden condition's ``effect_refs`` includes a scheduled
    ``effect.set_asset_status`` event that targets it. Target resolution mirrors
    :func:`aegis_simulation_domain.world_state.WorldState.seed_queue` and
    ``SimulationRuntime._resolve_status_effect_target`` exactly: explicit
    ``targetAssetId``/``config.assetId`` wins, else the target of a generator named in the
    condition's ``trigger_refs``.
    """
    scheduled_by_id = {event.id: event for event in manifest.scheduled_events}
    generator_by_id = {gen.id: gen for gen in manifest.generators}
    asset_baseline_risk = {asset.id: asset.initial_risk_score for asset in manifest.assets}
    asset_baseline_status = {asset.id: asset.initial_status for asset in manifest.assets}

    condition_ids_by_asset: dict[str, set[str]] = {}
    for condition in manifest.hidden_conditions:
        for effect_ref in condition.effect_refs:
            scheduled = scheduled_by_id.get(effect_ref)
            if scheduled is None or scheduled.action.plugin_id != _SET_STATUS_PLUGIN:
                continue
            asset_id = _resolve_effect_asset(scheduled, condition, generator_by_id)
            if asset_id is None:
                continue
            condition_ids_by_asset.setdefault(asset_id, set()).add(condition.id)

    return {
        asset_id: GovernedAsset(
            asset_id=asset_id,
            condition_ids=frozenset(condition_ids),
            baseline_risk=asset_baseline_risk.get(asset_id, 0.0),
            baseline_status=asset_baseline_status.get(asset_id, REDACTED_STATUS),
        )
        for asset_id, condition_ids in condition_ids_by_asset.items()
    }


def _resolve_effect_asset(
    scheduled: ScheduledEventDefinitionV1,
    condition: HiddenConditionDefinitionV1,
    generator_by_id: dict[str, GeneratorDefinitionV1],
) -> str | None:
    if scheduled.target_asset_id:
        return str(scheduled.target_asset_id)
    asset_from_config = scheduled.action.config.get("assetId")
    if isinstance(asset_from_config, str) and asset_from_config:
        return asset_from_config
    for trigger_ref in condition.trigger_refs:
        generator = generator_by_id.get(trigger_ref)
        if generator is not None and generator.target_asset_id:
            return str(generator.target_asset_id)
    return None


@dataclass(frozen=True)
class DisclosureInputs:
    """Event-derived inputs that decide, per run, which governed assets are disclosed."""

    revealed_condition_ids: frozenset[str] = frozenset()
    alerted_asset_ids: frozenset[str] = frozenset()


def is_asset_disclosed(
    asset_id: str,
    governing_map: dict[str, GovernedAsset],
    inputs: DisclosureInputs,
) -> bool:
    governed = governing_map.get(asset_id)
    if governed is None:
        return True
    if asset_id in inputs.alerted_asset_ids:
        return True
    return any(cid in inputs.revealed_condition_ids for cid in governed.condition_ids)


def disclosed_asset_ids(
    asset_ids: Iterable[str],
    governing_map: dict[str, GovernedAsset],
    inputs: DisclosureInputs,
) -> set[str]:
    return {
        asset_id
        for asset_id in asset_ids
        if is_asset_disclosed(asset_id, governing_map, inputs)
    }


def disclosure_inputs_from_events(
    events: Iterable[DomainEventEnvelopeV1],
) -> DisclosureInputs:
    """Derive disclosure inputs purely from a slice of the event stream.

    Used where disclosure must reflect what the operator knew *as of* a point in the stream
    (mid-run replay): pass only the events up to the target sequence. Deterministic — the
    same slice always yields the same disclosure.
    """
    revealed: set[str] = set()
    alerted: set[str] = set()
    for event in events:
        if event.type == _REVEALED_EVENT:
            condition_id = event.payload.get("conditionId")
            if isinstance(condition_id, str):
                revealed.add(condition_id)
        elif event.type.startswith(_ALERT_PREFIX):
            asset_id = event.payload.get("assetId")
            if isinstance(asset_id, str) and asset_id:
                alerted.add(asset_id)
    return DisclosureInputs(
        revealed_condition_ids=frozenset(revealed),
        alerted_asset_ids=frozenset(alerted),
    )


def redact_graph_snapshot(
    snapshot: GraphSnapshotV1,
    governing_map: dict[str, GovernedAsset],
    inputs: DisclosureInputs,
) -> GraphSnapshotV1:
    """Return an operator-safe copy of a graph snapshot.

    Undisclosed governed nodes are shown at their baseline status with ``disclosed=false``
    and their risk clamped to the manifest baseline (no attacker-driven spike leaks). All
    other nodes pass through with ``disclosed=true``. The input snapshot is never mutated.
    """
    if not governing_map:
        return snapshot

    changed = False
    new_nodes = []
    for node in snapshot.nodes:
        if is_asset_disclosed(node.id, governing_map, inputs):
            if node.disclosed is not True:
                node = node.model_copy(update={"disclosed": True})
                changed = True
            new_nodes.append(node)
            continue
        governed = governing_map.get(node.id)
        baseline_risk = governed.baseline_risk if governed is not None else node.risk_score
        new_nodes.append(
            node.model_copy(
                update={
                    "status": REDACTED_STATUS,
                    "disclosed": False,
                    "risk_score": min(node.risk_score, baseline_risk),
                }
            )
        )
        changed = True

    if not changed:
        return snapshot
    return snapshot.model_copy(update={"nodes": new_nodes})


@dataclass(frozen=True)
class TriggeredCondition:
    condition_id: str
    triggered_at: datetime


@dataclass
class ThreatTempoState:
    """Inputs for the per-run threat-tempo scalar (all sim-time derived)."""

    current_sim_time: datetime
    triggered: list[TriggeredCondition] = field(default_factory=list)
    revealed_condition_ids: frozenset[str] = frozenset()
    disclosed_condition_ids: frozenset[str] = frozenset()
    total_conditions: int = 0


def compute_threat_tempo(
    state: ThreatTempoState,
    *,
    saturation_sim_seconds: float,
) -> float:
    """Return an ambient pressure scalar in ``[0, 1]`` — higher = more undetected attack.

    Pressure accrues from hidden conditions the attacker has *triggered* but the operator
    has not yet *disclosed* (neither revealed in sim state nor surfaced by an alert). Each
    undisclosed triggered condition contributes a weight that ramps linearly from 0 to 1
    over ``saturation_sim_seconds`` since it triggered — the longer an attack beat sits
    undetected, the more it presses. Disclosing a condition (reveal or alert) relieves its
    pressure entirely. The sum is normalised by the scenario's hidden-condition count so a
    fully-detected run reads 0 and a fully-undetected, long-dwelling run approaches 1.

    Scalar only: never exposes which condition or asset is driving it.
    """
    if state.total_conditions <= 0 or saturation_sim_seconds <= 0:
        return 0.0
    disclosed = state.revealed_condition_ids | state.disclosed_condition_ids
    pressure = 0.0
    for condition in state.triggered:
        if condition.condition_id in disclosed:
            continue
        elapsed = (state.current_sim_time - condition.triggered_at).total_seconds()
        pressure += _clamp(elapsed / saturation_sim_seconds, 0.0, 1.0)
    return _clamp(pressure / state.total_conditions, 0.0, 1.0)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))

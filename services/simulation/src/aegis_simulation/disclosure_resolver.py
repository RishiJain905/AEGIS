"""Per-run fog-of-war disclosure resolution over live persisted state.

Gathers the two event-derived inputs the pure disclosure model needs — which governing
hidden conditions have been *revealed* and which assets a persisted *alert* references —
and pairs them with the scenario's static governing map. Consumed by the operator-facing
snapshot transports (GET /graph, bootstrap) and, indirectly, the live WebSocket path.

Detection/ML/scoring never call this; they read full truth. This only feeds the transport
that reaches the human operator.
"""

from __future__ import annotations

from dataclasses import dataclass

from aegis_persistence.repositories.postgres import (
    PostgresAlertRepository,
    PostgresCheckpointRepository,
)
from aegis_scenario_sdk.contracts.manifest import ScenarioManifestV1
from aegis_simulation_domain.disclosure import (
    DisclosureInputs,
    GovernedAsset,
    build_governing_map,
    is_asset_disclosed,
)
from sqlalchemy.ext.asyncio import AsyncSession

# Statuses for which the operator graph is still fog-gated. Once a run reaches a terminal
# status the graph switches to full ground truth for debrief/after-action.
ACTIVE_RUN_STATUSES: frozenset[str] = frozenset({"created", "running", "paused"})


@dataclass(frozen=True)
class RunDisclosure:
    """Resolved fog state for one run at the current moment."""

    governing_map: dict[str, GovernedAsset]
    inputs: DisclosureInputs

    @property
    def has_hidden_state(self) -> bool:
        return bool(self.governing_map)

    def is_disclosed(self, asset_id: str) -> bool:
        return is_asset_disclosed(asset_id, self.governing_map, self.inputs)


def _empty(manifest: ScenarioManifestV1) -> RunDisclosure:
    return RunDisclosure(governing_map=build_governing_map(manifest), inputs=DisclosureInputs())


async def resolve_run_disclosure(
    session: AsyncSession,
    *,
    run_id: str,
    manifest: ScenarioManifestV1,
    revealed_condition_ids: frozenset[str] | None = None,
) -> RunDisclosure:
    """Resolve current disclosure for a run.

    ``revealed_condition_ids`` may be supplied by a caller that already holds live runtime
    state (avoids a checkpoint read); otherwise reveals are read from the latest persisted
    checkpoint (refreshed every command/tick), which is far cheaper than scanning the event
    stream. Alerted assets always come from the persisted alert rows.
    """
    governing_map = build_governing_map(manifest)
    if not governing_map:
        return RunDisclosure(governing_map={}, inputs=DisclosureInputs())

    revealed = revealed_condition_ids
    if revealed is None:
        revealed = await _revealed_from_checkpoint(session, run_id)
    alerted = await _alerted_asset_ids(session, run_id)
    return RunDisclosure(
        governing_map=governing_map,
        inputs=DisclosureInputs(
            revealed_condition_ids=revealed,
            alerted_asset_ids=alerted,
        ),
    )


async def _revealed_from_checkpoint(session: AsyncSession, run_id: str) -> frozenset[str]:
    checkpoint = await PostgresCheckpointRepository(session).get_latest_for_run(run_id)
    if checkpoint is None:
        return frozenset()
    return frozenset(
        condition.condition_id
        for condition in checkpoint.world_state.hidden_conditions
        if condition.revealed
    )


async def _alerted_asset_ids(session: AsyncSession, run_id: str) -> frozenset[str]:
    alerts = await PostgresAlertRepository(session).list_by_run(run_id)
    return frozenset(alert.asset_id for alert in alerts if alert.asset_id)

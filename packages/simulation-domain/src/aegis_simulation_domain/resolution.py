"""Win/lose resolution for a run (pure function of world state).

The run is a race: the attacker advances toward exfiltration on the sim clock while the
defender hunts and severs. This module answers the one question that turns those surfaces
into a game — *is it over, and who won* — from nothing but the world state the runtime
already holds, so live play, checkpoint restore, and replay all resolve identically.

Resolution is monotonic and fire-once: the first condition to hold wins, the runtime
records it, and it never changes afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass

from aegis_contracts.killchain import (
    NEUTRALIZED_CAMPAIGN_STATUSES,
    CampaignStatus,
    RunOutcome,
    RunOutcomeReason,
)
from aegis_scenario_sdk.contracts.manifest import ProportionalityPolicyV1

from aegis_simulation_domain.disruption import BusinessDisruption
from aegis_simulation_domain.world_state import WorldState


@dataclass(frozen=True)
class RunResolution:
    """The verdict, plus the evidence the after-action needs to explain it."""

    outcome: RunOutcome
    reason: RunOutcomeReason
    disruption_cost: float
    peak_disruption_cost: float
    needless_critical_outages: tuple[str, ...]
    neutralized_campaign_ids: tuple[str, ...]
    succeeded_campaign_ids: tuple[str, ...]


def evaluate_run_outcome(
    *,
    world: WorldState,
    disruption: BusinessDisruption,
    peak_disruption_cost: float,
    policy: ProportionalityPolicyV1,
    horizon_reached: bool,
) -> RunResolution | None:
    """Return the run's verdict, or ``None`` while the race is still on.

    Ordering matters and is deliberate:

    1. **Exfiltration completed** loses immediately — the objective the whole run exists
       to protect is gone, and no amount of proportionality redeems that.
    2. **Over-containment** loses next. Crossing the cost fail-threshold, or needlessly
       taking critical services the attacker never touched offline, is its own failure
       mode: you cannot save the org by destroying it.
    3. **Every campaign neutralized** wins — costly if containment crossed the warning
       threshold at any point during the run, clean otherwise.
    4. **Horizon elapsed** with the attacker still moving is unresolved: nobody won, and
       scoring grades how far it got against how well you responded.
    """
    succeeded = tuple(
        sorted(
            campaign_id
            for campaign_id, state in world.campaigns.items()
            if state.status == CampaignStatus.SUCCEEDED.value
        )
    )
    neutralized = tuple(
        sorted(
            campaign_id
            for campaign_id, state in world.campaigns.items()
            if state.status in NEUTRALIZED_CAMPAIGN_STATUSES
        )
    )

    def resolution(outcome: RunOutcome, reason: RunOutcomeReason) -> RunResolution:
        return RunResolution(
            outcome=outcome,
            reason=reason,
            disruption_cost=disruption.cost,
            peak_disruption_cost=peak_disruption_cost,
            needless_critical_outages=disruption.needless_critical_outages,
            neutralized_campaign_ids=neutralized,
            succeeded_campaign_ids=succeeded,
        )

    if succeeded:
        return resolution(RunOutcome.LOSS_EXFILTRATION, RunOutcomeReason.EXFILTRATION_COMPLETED)

    if len(disruption.needless_critical_outages) >= policy.needless_critical_outage_limit:
        return resolution(
            RunOutcome.LOSS_OVER_CONTAINMENT, RunOutcomeReason.CRITICAL_SERVICES_CRIPPLED
        )
    if disruption.cost >= policy.fail_threshold:
        return resolution(
            RunOutcome.LOSS_OVER_CONTAINMENT, RunOutcomeReason.OVER_CONTAINMENT_COST
        )

    if world.campaigns and all(
        state.status in NEUTRALIZED_CAMPAIGN_STATUSES for state in world.campaigns.values()
    ):
        costly = peak_disruption_cost >= policy.warn_threshold
        return resolution(
            RunOutcome.COSTLY_WIN if costly else RunOutcome.WIN,
            RunOutcomeReason.ALL_CAMPAIGNS_NEUTRALIZED,
        )

    if horizon_reached:
        return resolution(RunOutcome.UNRESOLVED, RunOutcomeReason.HORIZON_ELAPSED)

    return None

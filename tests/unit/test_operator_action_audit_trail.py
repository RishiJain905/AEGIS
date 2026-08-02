"""Offline guards on the operator direct-action audit trail and its execution wiring.

Both invariants here failed silently in production rather than loudly in a test, which is
why they are pinned at this level: an executed containment that mutates the wrong runtime
still returns HTTP 200, and an audit event missing the operator's reason still validates.
"""

from __future__ import annotations

from aegis_agents.runtime.ids import new_runtime_id
from aegis_api.approvals.service import ApprovalWorkflowService
from aegis_api.operator_actions.events import build_operator_action_proposed_event
from aegis_api.runs.service import get_run_command_service


def test_approval_execution_runs_on_the_shared_runtime_cache() -> None:
    """Execution must mutate the runtime the tick engine steps, not a private copy.

    The approval service used to construct its own :class:`RunCommandService`, so every
    approved containment applied its effect to a throwaway world: the asset never gained the
    control, the disruption model never saw the foothold severed, and the operator-facing
    graph never showed a badge. Nothing downstream could repair it either — a cached runtime
    skips its ``next_sequence`` past out-of-band events without applying them, so the next
    checkpoint stranded the effect behind the restore cursor for good.
    """
    service = ApprovalWorkflowService()
    assert service._run_commands is get_run_command_service()


def test_proposed_event_records_the_operator_justification() -> None:
    """The reason typed into the consequence gate belongs in the persisted event.

    It used to live only on the proposal row, so the feed, replay and the after-action could
    all say a Class 2 containment ran but none of them could say why.
    """
    event = build_operator_action_proposed_event(
        event_id=new_runtime_id("evt"),
        run_id=new_runtime_id("run"),
        sequence=1,
        actor_id="user:operator",
        trace_id=new_runtime_id("trc"),
        proposal_id=new_runtime_id("prp"),
        incident_id="incident:inc_test",
        scenario_command="isolate",
        action_class="class_2",
        target_asset_id="asset:svc-identity-broker",
        justification="Broker is beaconing to the staging bucket.",
    )
    assert event.payload["justification"] == "Broker is beaconing to the staging bucket."
    assert event.payload["initiator"] == "operator"

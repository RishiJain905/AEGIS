"""The grounding contract: show the model the ids, then repair once if it misses.

Every one of these runs offline against a fake generation facade — no provider, no
database — because the behaviour under test is exactly the one CI must protect
without an LLM: what the request tells the model about evidence ids, and what the
runtime does with an answer that cites an id this run has never heard of.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from aegis_agents.runtime.executor import (
    MAX_GROUNDING_REPAIR_ROUNDS,
    TaskExecutor,
    _LoopOutcome,
    _PreparedTask,
)
from aegis_agents.runtime.grounding import (
    MAX_CATALOGUE_EVIDENCE,
    build_evidence_catalogue,
    catalogue_ids,
    invalid_citation_ids,
)
from aegis_agents.security.scenario_content import (
    build_evidence_catalogue_message,
    build_grounding_correction_message,
)
from aegis_contracts.agent_runtime import AgentTaskStatus, AgentTaskV1
from aegis_contracts.entities import EvidenceV1
from aegis_contracts.generation import (
    GenerationMessageRole,
    GenerationMessageV1,
    GenerationRequestV1,
    GenerationResponseV1,
    ModelConfigV1,
    ProviderErrorCode,
    ProviderErrorV1,
    ProviderFinishReason,
    ProviderGenerateResponseV1,
    ProviderUsageV1,
    StructuredOutputSpecV1,
)
from aegis_contracts.versioning import (
    AGENT_TASK_SCHEMA_VERSION,
    EVIDENCE_SCHEMA_VERSION,
    GENERATION_REQUEST_SCHEMA_VERSION,
    GENERATION_RESPONSE_SCHEMA_VERSION,
    MODEL_CONFIG_SCHEMA_VERSION,
    PROVIDER_ERROR_SCHEMA_VERSION,
    PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION,
    PROVIDER_USAGE_SCHEMA_VERSION,
    STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
)

_VISIBLE = "evidence:evd_real_001"
_OTHER_VISIBLE = "evidence:evd_real_002"
_HALLUCINATED = "ALERT-001"
_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_TRACE_ID = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"


def _evidence(index: int) -> EvidenceV1:
    return EvidenceV1(
        schema_version=EVIDENCE_SCHEMA_VERSION,
        id=f"evidence:evd_real_{index:03d}",
        run_id=_RUN_ID,
        source_event_id="evt_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        summary=f"Observation {index}",
        asset_id="asset:idp-primary",
        created_at=_NOW,
    )


def _answer(*evidence_ids: str) -> dict[str, Any]:
    return {
        "rationale": "The identity provider shows anomalous authentication.",
        "confidence": 0.6,
        "evidenceCitations": [{"evidenceId": eid, "rationale": "supports"} for eid in evidence_ids],
        "toolRequests": [],
    }


def _response(payload: dict[str, Any]) -> ProviderGenerateResponseV1:
    return ProviderGenerateResponseV1(
        schema_version=PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION,
        response=GenerationResponseV1(
            schema_version=GENERATION_RESPONSE_SCHEMA_VERSION,
            request_id="gen_01ARZ3NDEKTSV4RRFFQ69G5FAW",
            trace_id=_TRACE_ID,
            provider_id="mock",
            model_id="mock-model",
            prompt_version="v1",
            content=json.dumps(payload),
            structured_data=payload,
            finish_reason=ProviderFinishReason.STOP,
            usage=ProviderUsageV1(
                schema_version=PROVIDER_USAGE_SCHEMA_VERSION,
                prompt_tokens=10,
                completion_tokens=10,
                total_tokens=20,
            ),
            latency_ms=5,
            completed_at=_NOW,
        ),
    )


def _error_response() -> ProviderGenerateResponseV1:
    return ProviderGenerateResponseV1(
        schema_version=PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION,
        error=ProviderErrorV1(
            schema_version=PROVIDER_ERROR_SCHEMA_VERSION,
            code=ProviderErrorCode.TIMEOUT,
            message="provider timed out",
            retryable=True,
        ),
    )


class _RecordingGeneration:
    """A generation facade that replays scripted answers and records the requests."""

    def __init__(self, *responses: ProviderGenerateResponseV1) -> None:
        self._responses = list(responses)
        self.requests: list[GenerationRequestV1] = []

    async def generate(
        self,
        request: GenerationRequestV1,
        *,
        dry_run: bool = False,
    ) -> ProviderGenerateResponseV1:
        self.requests.append(request)
        if not self._responses:
            msg = "generation called more times than the test scripted"
            raise AssertionError(msg)
        return self._responses.pop(0)


def _request() -> GenerationRequestV1:
    return GenerationRequestV1(
        schema_version=GENERATION_REQUEST_SCHEMA_VERSION,
        request_id="gen_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        trace_id=_TRACE_ID,
        provider_id="mock",
        model_config_ref=ModelConfigV1(
            schema_version=MODEL_CONFIG_SCHEMA_VERSION,
            provider_id="mock",
            model_id="mock-model",
            prompt_version="v1",
        ),
        messages=[
            GenerationMessageV1(role=GenerationMessageRole.SYSTEM, content="system"),
            GenerationMessageV1(role=GenerationMessageRole.USER, content="user"),
        ],
        structured_output=StructuredOutputSpecV1(
            schema_version=STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
            json_schema={"type": "object"},
            strict=True,
            max_repair_attempts=1,
        ),
    )


@dataclass
class _Fixture:
    executor: TaskExecutor
    generation: _RecordingGeneration
    prepared: _PreparedTask
    outcome: _LoopOutcome


def _fixture(
    *,
    first: dict[str, Any],
    scripted: list[ProviderGenerateResponseV1],
) -> _Fixture:
    generation = _RecordingGeneration(*scripted)
    executor = TaskExecutor(generation=generation)  # type: ignore[arg-type]
    task = AgentTaskV1(
        schema_version=AGENT_TASK_SCHEMA_VERSION,
        id="atk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        session_id="agent-session:ags_grounding",
        run_id=_RUN_ID,
        incident_id="incident:inc_grounding",
        status=AgentTaskStatus.RUNNING,
        idempotency_key="grounding-1",
        trace_id=_TRACE_ID,
        provider_id="mock",
        created_at=_NOW,
        updated_at=_NOW,
    )
    prepared = _PreparedTask(
        task=task,
        session=None,
        run_id=_RUN_ID,
        agent_name="WATCHTOWER",
        definition=None,
        budget=None,
        incident_title="Case",
        run_scoped=False,
        visible_ids={_VISIBLE, _OTHER_VISIBLE},
        role_handler=None,
        request=_request(),
        evidence_catalogue=build_evidence_catalogue([_evidence(1), _evidence(2)]),
    )
    request = _request()
    outcome = _LoopOutcome(
        response=_response(first),
        request=request,
        pending_tool_requests=[],
        executed_tool_count=0,
        iterations=0,
        # Generous runway so the repair is never skipped for lack of time; the
        # floor is exercised separately by the "no runway" test below.
        deadline_monotonic=float("inf"),
    )
    return _Fixture(executor=executor, generation=generation, prepared=prepared, outcome=outcome)


# --- prevention: the model is shown the ids it is required to cite --------------


def test_catalogue_carries_the_ids_and_the_true_total() -> None:
    catalogue = build_evidence_catalogue([_evidence(i) for i in range(1, 4)])
    assert catalogue["total"] == 3
    assert catalogue["truncated"] is False
    assert catalogue_ids(catalogue) == [
        "evidence:evd_real_001",
        "evidence:evd_real_002",
        "evidence:evd_real_003",
    ]


def test_catalogue_is_bounded_and_keeps_the_newest() -> None:
    evidence = [_evidence(i) for i in range(1, MAX_CATALOGUE_EVIDENCE + 6)]
    catalogue = build_evidence_catalogue(evidence)
    assert catalogue["total"] == len(evidence)
    assert catalogue["shown"] == MAX_CATALOGUE_EVIDENCE
    assert catalogue["truncated"] is True
    assert catalogue_ids(catalogue)[-1] == evidence[-1].id


def test_catalogue_message_states_the_verbatim_rule_and_the_empty_out() -> None:
    message = build_evidence_catalogue_message(build_evidence_catalogue([_evidence(1)]))
    assert "VERBATIM" in message.content
    assert "empty evidenceCitations array" in message.content
    assert _VISIBLE in message.content


def test_correction_message_names_the_rejected_and_the_valid_ids() -> None:
    message = build_grounding_correction_message(
        invalid_ids=[_HALLUCINATED],
        valid_ids=[_VISIBLE, _OTHER_VISIBLE],
    )
    assert _HALLUCINATED in message.content
    assert _VISIBLE in message.content
    assert "rejectedEvidenceIds" in message.content


def _catalogue_uow(evidence: list[EvidenceV1]) -> Any:
    """The slice of the unit of work ``_build_request`` reads."""

    class _Uow:
        pass

    uow = _Uow()

    class _Evidence:
        async def list_for_run(self, run_id: str) -> list[EvidenceV1]:
            return evidence

    class _Empty:
        async def list_by_run(self, run_id: str) -> list[Any]:
            return []

        async def list_for_session(self, session_id: str) -> list[Any]:
            return []

    class _Runs:
        async def get_by_id(self, run_id: str) -> None:
            return None

    uow.evidence = _Evidence()
    uow.alerts = _Empty()
    uow.incidents = _Empty()
    uow.agent_tasks = _Empty()
    uow.agent_artifacts = _Empty()
    uow.tool_invocations = _Empty()
    uow.runs = _Runs()
    return uow


@pytest.mark.asyncio
@pytest.mark.parametrize("incident_id", ["incident:inc_grounding", None])
async def test_the_request_shows_the_model_the_ids_it_will_be_validated_against(
    incident_id: str | None,
) -> None:
    """The defect in one assertion.

    The audit path validates citations against the run's visible evidence ids —
    and used to send a request that never mentioned a single one of them, while
    requiring an ``evidenceCitations`` field. Inventing an id was the only move
    the schema left. Both scopes must now carry the catalogue, and it must agree
    exactly with the set the validator will use.
    """
    from aegis_agents.runtime.registry import build_definition
    from aegis_contracts.entities import AgentRole, AgentSessionState, AgentSessionV1
    from aegis_contracts.versioning import AGENT_SESSION_SCHEMA_VERSION

    evidence = [_evidence(1), _evidence(2)]
    definition = build_definition(AgentRole.WATCHTOWER, provider_id="mock")
    session = AgentSessionV1(
        schema_version=AGENT_SESSION_SCHEMA_VERSION,
        id="agent-session:ags_grounding",
        run_id=_RUN_ID,
        incident_id=incident_id,
        role=AgentRole.WATCHTOWER,
        state=AgentSessionState.GATHERING,
        trace_id=_TRACE_ID,
        created_at=_NOW,
        updated_at=_NOW,
    )
    task = AgentTaskV1(
        schema_version=AGENT_TASK_SCHEMA_VERSION,
        id="atk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        session_id=session.id,
        run_id=_RUN_ID,
        incident_id=incident_id,
        status=AgentTaskStatus.RUNNING,
        idempotency_key="grounding-1",
        trace_id=_TRACE_ID,
        provider_id="mock",
        created_at=_NOW,
        updated_at=_NOW,
    )
    executor = TaskExecutor(generation=None)  # type: ignore[arg-type]
    request, _, visible_ids, _, catalogue = await executor._build_request(
        _catalogue_uow(evidence),
        task=task,
        session=session,
        run_id=_RUN_ID,
        incident_title="Case",
        definition=definition,
        budget=definition.default_budget,
    )

    assert set(catalogue_ids(catalogue)) == visible_ids
    # Last message, so it is the most recent thing read before answering and sits
    # after (and cannot be reframed by) the untrusted operator text above it.
    last = request.messages[-1].content
    assert "AEGIS_EVIDENCE_CATALOGUE" in last
    for item in evidence:
        assert item.id in last


# --- detection: which ids are actually wrong ------------------------------------


def test_invalid_citation_ids_names_only_the_unknown_ids() -> None:
    structured = _answer(_VISIBLE, _HALLUCINATED)
    assert invalid_citation_ids(structured, visible_evidence_ids={_VISIBLE}) == [_HALLUCINATED]


def test_invalid_citation_ids_deduplicates_one_repeated_mistake() -> None:
    structured = _answer(_HALLUCINATED, _HALLUCINATED, _HALLUCINATED)
    assert invalid_citation_ids(structured, visible_evidence_ids={_VISIBLE}) == [_HALLUCINATED]


def test_grounded_answer_reports_nothing_invalid() -> None:
    structured = _answer(_VISIBLE, _OTHER_VISIBLE)
    assert invalid_citation_ids(structured, visible_evidence_ids={_VISIBLE, _OTHER_VISIBLE}) == []


@pytest.mark.parametrize(
    "citations",
    [
        "not-a-list",
        {"evidenceId": _VISIBLE},
        [None],
        [{"rationale": "no id at all"}],
    ],
)
def test_shape_faults_are_left_to_the_provider_repair(citations: Any) -> None:
    """A malformed citations FIELD is a schema fault, not a grounding one.

    Re-prompting it with "these ids are invalid" would send the model chasing the
    wrong problem; the provider's own structured-output repair owns this shape.
    """
    structured = {"rationale": "x", "confidence": 0.5, "evidenceCitations": citations}
    assert invalid_citation_ids(structured, visible_evidence_ids={_VISIBLE}) == []


# --- repair: one bounded corrective round-trip ----------------------------------


@pytest.mark.asyncio
async def test_grounded_answer_costs_no_repair_call() -> None:
    fixture = _fixture(first=_answer(_VISIBLE), scripted=[])
    result = await fixture.executor._repair_grounding(fixture.prepared, fixture.outcome)
    assert fixture.generation.requests == []
    assert result.response is fixture.outcome.response


@pytest.mark.asyncio
async def test_hallucinated_id_is_repaired_and_the_corrected_answer_wins() -> None:
    fixture = _fixture(
        first=_answer(_HALLUCINATED),
        scripted=[_response(_answer(_VISIBLE))],
    )
    result = await fixture.executor._repair_grounding(fixture.prepared, fixture.outcome)

    assert len(fixture.generation.requests) == MAX_GROUNDING_REPAIR_ROUNDS
    correction = fixture.generation.requests[0].messages[-1].content
    assert _HALLUCINATED in correction
    assert _VISIBLE in correction

    cited = result.response.response.structured_data["evidenceCitations"]
    assert [item["evidenceId"] for item in cited] == [_VISIBLE]
    # The superseded answer's cost is banked so the task still reports what it spent.
    assert result.extra_tokens == 20


@pytest.mark.asyncio
async def test_a_repair_that_hallucinates_again_keeps_the_original_answer() -> None:
    original = _answer(_HALLUCINATED)
    fixture = _fixture(first=original, scripted=[_response(_answer("EV001"))])
    result = await fixture.executor._repair_grounding(fixture.prepared, fixture.outcome)

    assert len(fixture.generation.requests) == 1
    assert result.response.response.structured_data == original
    assert result.extra_tokens == 0


@pytest.mark.asyncio
async def test_a_failing_repair_call_leaves_the_turn_exactly_as_it_was() -> None:
    original = _answer(_HALLUCINATED)
    fixture = _fixture(first=original, scripted=[_error_response()])
    result = await fixture.executor._repair_grounding(fixture.prepared, fixture.outcome)
    assert result.response.response.structured_data == original


@pytest.mark.asyncio
async def test_repair_never_runs_twice_for_one_turn() -> None:
    """The bound is the point: a model that cannot cite from a list it was just
    handed will not manage it on the third try, and each round is a full call."""
    fixture = _fixture(
        first=_answer(_HALLUCINATED),
        scripted=[_response(_answer("EV001")), _response(_answer(_VISIBLE))],
    )
    await fixture.executor._repair_grounding(fixture.prepared, fixture.outcome)
    assert len(fixture.generation.requests) == 1


@pytest.mark.asyncio
async def test_repair_carries_the_whole_conversation_forward() -> None:
    """Tool results and the catalogue must survive into the corrective call —
    a repair that dropped them would be asking a differently-informed model."""
    fixture = _fixture(first=_answer(_HALLUCINATED), scripted=[_response(_answer(_VISIBLE))])
    await fixture.executor._repair_grounding(fixture.prepared, fixture.outcome)
    repair_messages = fixture.generation.requests[0].messages
    assert [m.content for m in repair_messages[:2]] == ["system", "user"]
    assert len(repair_messages) == 3

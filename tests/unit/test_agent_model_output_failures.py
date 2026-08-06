"""A local model's bad answers must fail the task legibly, never crash persistence.

Chrome QA drove WATCHTOWER against the live local model and hit two failures that
looked like platform bugs but were not:

* the model cited ``EVT-ALERT-001`` — not an AEGIS identifier at all — and the
  authored-id validator inside the domain contracts raised
  ``ContractValidationError`` from deep inside the persist phase. The operator saw
  ``INTERNAL: Agent task failed``, which names neither the id nor the model;
* a malformed answer was reported as ``PROVIDER_FAILURE``, sending whoever read it
  to check an endpoint that was working perfectly.

Both are diagnosis bugs with the same shape: a fault in the *model's output*
wearing the costume of a fault in the *platform*. These tests pin the distinction.
The turn still fails when grounding cannot be trusted — a hallucinated citation
must never be persisted as if it were real — but it fails as a named, retryable
``STRUCTURED_OUTPUT_INVALID`` carrying the offending value.

No provider and no database: everything here is a fake.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.executor import TaskExecutor, _LoopOutcome, _PreparedTask
from aegis_agents.runtime.grounding import build_evidence_catalogue
from aegis_agents.runtime.registry import build_definition
from aegis_contracts.agent_runtime import (
    AgentBudgetV1,
    AgentTaskStatus,
    AgentTaskV1,
)
from aegis_contracts.entities import AgentRole
from aegis_contracts.errors import ContractErrorCode, ContractValidationError
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
    AGENT_BUDGET_SCHEMA_VERSION,
    AGENT_TASK_SCHEMA_VERSION,
    GENERATION_REQUEST_SCHEMA_VERSION,
    GENERATION_RESPONSE_SCHEMA_VERSION,
    MODEL_CONFIG_SCHEMA_VERSION,
    PROVIDER_ERROR_SCHEMA_VERSION,
    PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION,
    PROVIDER_USAGE_SCHEMA_VERSION,
    STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
)

_RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_INCIDENT_ID = "incident:inc_silent_relay_001"
_VISIBLE_EVIDENCE_ID = "evidence:evd_auth_burst_001"
_NOW = datetime(2026, 7, 31, 9, 0, tzinfo=UTC)

# Verbatim from a live probe of the local model (Qwimi 27B, no server-side
# grammar): asked to triage an incident whose prompt carries no real identifiers,
# it invents plausible-looking ones. These are the exact strings it produced.
_HALLUCINATED_EVIDENCE_ID = "LOG-2024-0892-001"
_HALLUCINATED_ALERT_ID = "AUTH-2024-0892-001"


def _runtime_id(prefix: str, index: int = 1) -> str:
    return f"{prefix}_{index:026d}"


class _FakeRepo:
    def __init__(self, task: AgentTaskV1 | None = None) -> None:
        #: The task row the persist phase re-reads to detect an external
        #: cancellation; None means "no row" for the other repos.
        self.task = task

    async def get_by_id(self, _id: str) -> Any:
        return self.task

    async def next_sequence(self, _run_id: str) -> int:
        return 1

    async def update(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def add(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def claim_transition(
        self, _task: Any, *, from_statuses: tuple[str, ...]
    ) -> bool:
        return True


class _FakeSessionLike:
    """The slice of a SQLAlchemy session the persist phase touches."""

    def expire_all(self) -> None:
        return None


class _FakeUow:
    def __init__(self, task: AgentTaskV1 | None = None) -> None:
        self.session = _FakeSessionLike()
        self.agent_sessions = _FakeRepo()
        self.agent_artifacts = _FakeRepo()
        self.agent_tasks = _FakeRepo(task)
        self.events = _FakeRepo()
        self.runs = _FakeRepo()
        self.appended_events: list[Any] = []

    async def append_event(self, envelope: Any) -> Any:
        self.appended_events.append(envelope)
        return envelope

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class _FakeSession:
    id = "agent-session:ags_watchtower_001"
    role = AgentRole.WATCHTOWER
    incident_id = _INCIDENT_ID


class _PassThroughSessions:
    """The session service, minus the state machine and its event appends."""

    async def transition(self, _uow: Any, *, session: Any, **_kwargs: Any) -> Any:
        return session


class _RaisingRoleHandler:
    """A role handler whose post-processing hits an authored-id validator.

    Stands in for all six real ones. Every role feeds the model's own payload into
    domain contracts with authored-id fields — WATCHTOWER's ``alertIds`` and
    ``evidenceIds``, TRACE's ``seedAssetIds``, BASTION's ``targetAssetId`` — so
    they all fail this way, and the containment has to sit above them rather than
    be re-implemented six times.
    """

    def output_schema(self) -> dict[str, Any]:
        return {"type": "object"}

    def system_prompt(self) -> str:
        return "handler"

    async def post_process(self, *, ctx: Any, structured: dict[str, Any]) -> None:
        raise ContractValidationError(
            code=ContractErrorCode.INVALID_IDENTIFIER,
            message=f"Invalid authored identifier: {_HALLUCINATED_ALERT_ID}",
            details={"value": _HALLUCINATED_ALERT_ID},
        )


def _budget() -> AgentBudgetV1:
    return AgentBudgetV1(
        schema_version=AGENT_BUDGET_SCHEMA_VERSION,
        max_tokens=8000,
        max_latency_ms=60_000,
        max_cost_usd=1.0,
    )


def _task(*, incident_id: str | None) -> AgentTaskV1:
    return AgentTaskV1(
        schema_version=AGENT_TASK_SCHEMA_VERSION,
        id=_runtime_id("atk"),
        session_id=_FakeSession.id,
        run_id=_RUN_ID,
        incident_id=incident_id,
        idempotency_key="triage-1",
        status=AgentTaskStatus.RUNNING,
        attempt=1,
        trace_id=_runtime_id("trc"),
        provider_id="openai-compatible",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _request() -> GenerationRequestV1:
    return GenerationRequestV1(
        schema_version=GENERATION_REQUEST_SCHEMA_VERSION,
        request_id=_runtime_id("gen"),
        trace_id=_runtime_id("trc"),
        provider_id="openai-compatible",
        model_config_ref=ModelConfigV1(
            schema_version=MODEL_CONFIG_SCHEMA_VERSION,
            provider_id="openai-compatible",
            model_id="openai-compatible-v1",
            prompt_version="phase20-watchtower-v1",
        ),
        messages=[
            GenerationMessageV1(
                role=GenerationMessageRole.SYSTEM,
                content="You are AEGIS WATCHTOWER.",
            )
        ],
        structured_output=StructuredOutputSpecV1(
            schema_version=STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
            json_schema={"type": "object"},
            strict=True,
            max_repair_attempts=1,
        ),
    )


def _answer(payload: dict[str, Any] | None, *, content: str | None = None) -> Any:
    return ProviderGenerateResponseV1(
        schema_version=PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION,
        response=GenerationResponseV1(
            schema_version=GENERATION_RESPONSE_SCHEMA_VERSION,
            request_id=_runtime_id("gen"),
            trace_id=_runtime_id("trc"),
            provider_id="openai-compatible",
            model_id="local-v1",
            prompt_version="phase20-watchtower-v1",
            content=json.dumps(payload) if content is None else content,
            structured_data=payload,
            finish_reason=ProviderFinishReason.STOP,
            usage=ProviderUsageV1(
                schema_version=PROVIDER_USAGE_SCHEMA_VERSION,
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
            ),
            latency_ms=7,
            completed_at=_NOW,
        ),
    )


def _failure(code: ProviderErrorCode, message: str) -> Any:
    return ProviderGenerateResponseV1(
        schema_version=PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION,
        error=ProviderErrorV1(
            schema_version=PROVIDER_ERROR_SCHEMA_VERSION,
            code=code,
            message=message,
        ),
    )


async def _persist(
    response: Any,
    *,
    run_scoped: bool = False,
    role_handler: Any = None,
    visible_ids: set[str] | None = None,
) -> _FakeUow:
    executor = TaskExecutor(generation=None)  # type: ignore[arg-type]
    executor._sessions = _PassThroughSessions()  # type: ignore[assignment]
    task = _task(incident_id=None if run_scoped else _INCIDENT_ID)
    uow = _FakeUow(task=task)
    prepared = _PreparedTask(
        task=task,
        session=_FakeSession(),
        run_id=_RUN_ID,
        agent_name="WATCHTOWER",
        definition=build_definition(AgentRole.WATCHTOWER, provider_id="openai-compatible"),
        budget=_budget(),
        incident_title="Suspicious authentication burst",
        run_scoped=run_scoped,
        visible_ids={_VISIBLE_EVIDENCE_ID} if visible_ids is None else visible_ids,
        role_handler=role_handler,
        request=_request(),
        evidence_catalogue=build_evidence_catalogue([]),
    )
    outcome = _LoopOutcome(
        response=response,
        request=prepared.request,
        pending_tool_requests=[],
        executed_tool_count=1,
        iterations=1,
    )
    await executor._persist_result(uow, prepared, outcome)  # type: ignore[arg-type]
    return uow


def _step(citations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rationale": "Authentication burst against the identity broker.",
        "confidence": 0.8,
        "evidenceCitations": citations,
        "toolRequests": [],
    }


# --- hallucinated identifiers -------------------------------------------------


@pytest.mark.asyncio
async def test_a_hallucinated_citation_id_fails_the_task_legibly() -> None:
    """The QA crash. It must reach the operator as a model fault naming the id."""
    with pytest.raises(AgentRuntimeError) as exc_info:
        await _persist(
            _answer(
                _step([{"evidenceId": _HALLUCINATED_EVIDENCE_ID, "rationale": "auth log"}])
            )
        )

    error = exc_info.value
    assert error.code is AgentRuntimeErrorCode.STRUCTURED_OUTPUT_INVALID
    assert error.retryable is True
    assert _HALLUCINATED_EVIDENCE_ID in error.message
    assert error.details["value"] == _HALLUCINATED_EVIDENCE_ID
    assert error.details["contractCode"] == ContractErrorCode.INVALID_IDENTIFIER.value


@pytest.mark.asyncio
async def test_the_contract_violation_never_escapes_as_itself() -> None:
    """Nothing above the executor should ever have to know about pydantic."""
    with pytest.raises(AgentRuntimeError):
        await _persist(_answer(_step([{"evidenceId": "EVT-ALERT-001"}])))


@pytest.mark.asyncio
async def test_a_well_formed_but_unknown_id_is_still_reported_as_not_visible() -> None:
    """The two failures are different and must stay different.

    A well-formed id the run does not contain is a *grounding* violation — the
    model cited real-looking evidence it was never shown. A malformed id is a
    *format* violation. Collapsing them would lose the more serious diagnosis.
    """
    with pytest.raises(AgentRuntimeError) as exc_info:
        await _persist(_answer(_step([{"evidenceId": "evidence:evd_never_seen_999"}])))

    assert exc_info.value.code is AgentRuntimeErrorCode.EVIDENCE_NOT_VISIBLE


@pytest.mark.asyncio
async def test_an_invalid_id_inside_role_post_processing_is_contained_too() -> None:
    """Citations are not the only door: every role writes model ids into contracts."""
    with pytest.raises(AgentRuntimeError) as exc_info:
        await _persist(
            _answer(_step([{"evidenceId": _VISIBLE_EVIDENCE_ID, "rationale": "seen"}])),
            role_handler=_RaisingRoleHandler(),
        )

    error = exc_info.value
    assert error.code is AgentRuntimeErrorCode.STRUCTURED_OUTPUT_INVALID
    assert error.retryable is True
    assert _HALLUCINATED_ALERT_ID in error.message
    assert "WATCHTOWER" in error.message


@pytest.mark.asyncio
async def test_a_grounded_incident_turn_still_completes() -> None:
    """The containment must not turn valid grounding into a failure."""
    uow = await _persist(
        _answer(_step([{"evidenceId": _VISIBLE_EVIDENCE_ID, "rationale": "auth burst"}]))
    )
    assert uow.appended_events, "the completion event should have been appended"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("label", "citations"),
    [
        ("a bare string where a list belongs", "evidence:evd_auth_burst_001"),
        ("null", None),
        ("a single object instead of a list of them", {"evidenceId": _VISIBLE_EVIDENCE_ID}),
        ("a list of bare id strings", [_VISIBLE_EVIDENCE_ID]),
    ],
)
async def test_the_chat_survives_citations_of_the_wrong_shape_entirely(
    label: str, citations: Any
) -> None:
    """The schema asks for a list of objects; a local model sends whatever it likes.

    Every one of these used to reach ``item.get(...)`` or ``for item in ...`` and
    raise out of the loop as an opaque ``INTERNAL`` crash. The chat's contract is
    that a malformed citation costs its own grounding, never the whole reply.
    """
    step = _step([])
    step["evidenceCitations"] = citations

    uow = await _persist(_answer(step), run_scoped=True)

    assert uow.appended_events, label


@pytest.mark.asyncio
async def test_the_audit_path_names_a_wrong_shaped_citations_field() -> None:
    """The chat's leniency is not the audit path's contract.

    An incident turn that produced no usable grounding must say so, not quietly
    persist an artifact that reads as if the model cited nothing on purpose.
    """
    step = _step([])
    step["evidenceCitations"] = _VISIBLE_EVIDENCE_ID

    with pytest.raises(AgentRuntimeError) as exc_info:
        await _persist(_answer(step))

    error = exc_info.value
    assert error.code is AgentRuntimeErrorCode.STRUCTURED_OUTPUT_INVALID
    assert error.retryable is True
    assert error.details["receivedType"] == "str"


@pytest.mark.asyncio
async def test_the_run_scoped_chat_still_drops_bad_ids_instead_of_failing() -> None:
    """Unchanged, and deliberately so.

    The interactive chat trades strictness for a usable reply: hallucinated
    citations are dropped, the grounded rationale still lands, and nothing
    ungrounded is ever presented as evidence.
    """
    uow = await _persist(
        _answer(
            _step(
                [
                    {"evidenceId": _HALLUCINATED_EVIDENCE_ID, "rationale": "invented"},
                    {"evidenceId": _VISIBLE_EVIDENCE_ID, "rationale": "real"},
                ]
            )
        ),
        run_scoped=True,
    )
    assert uow.appended_events


# --- provider vs model fault --------------------------------------------------


@pytest.mark.asyncio
async def test_malformed_model_output_is_not_reported_as_a_provider_fault() -> None:
    """"Model output is not valid JSON" is not a provider failure.

    The endpoint answered; the answer was wrong. Labelling that PROVIDER_FAILURE
    (and non-retryable) told the operator to go debug a healthy endpoint.
    """
    with pytest.raises(AgentRuntimeError) as exc_info:
        await _persist(
            _failure(
                ProviderErrorCode.STRUCTURED_OUTPUT_INVALID,
                "Model output is not valid JSON",
            )
        )

    error = exc_info.value
    assert error.code is AgentRuntimeErrorCode.STRUCTURED_OUTPUT_INVALID
    assert error.retryable is True
    assert "malformed output" in error.message
    assert error.details["providerCode"] == "STRUCTURED_OUTPUT_INVALID"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "retryable"),
    [
        (ProviderErrorCode.PROVIDER_UNAVAILABLE, True),
        (ProviderErrorCode.TIMEOUT, True),
        (ProviderErrorCode.RETRY_EXHAUSTED, True),
        (ProviderErrorCode.CREDENTIALS_MISSING, False),
        (ProviderErrorCode.OUTPUT_LIMIT_EXCEEDED, False),
    ],
)
async def test_real_provider_faults_are_still_provider_faults(
    code: ProviderErrorCode, retryable: bool
) -> None:
    with pytest.raises(AgentRuntimeError) as exc_info:
        await _persist(_failure(code, "endpoint problem"))

    assert exc_info.value.code is AgentRuntimeErrorCode.PROVIDER_FAILURE
    assert exc_info.value.retryable is retryable


@pytest.mark.asyncio
async def test_prose_in_the_content_fallback_is_a_model_fault_not_a_crash() -> None:
    """The last-resort read of ``content`` used to raise a bare JSONDecodeError."""
    with pytest.raises(AgentRuntimeError) as exc_info:
        await _persist(_answer(None, content="I was unable to complete the triage."))

    assert exc_info.value.code is AgentRuntimeErrorCode.STRUCTURED_OUTPUT_INVALID
    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_a_json_array_where_an_object_belongs_is_a_model_fault() -> None:
    with pytest.raises(AgentRuntimeError) as exc_info:
        await _persist(_answer(None, content='["not", "an", "object"]'))

    assert exc_info.value.code is AgentRuntimeErrorCode.STRUCTURED_OUTPUT_INVALID

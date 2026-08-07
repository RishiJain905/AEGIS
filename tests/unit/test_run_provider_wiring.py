"""A run's chosen model provider must reach every generation it causes — and only that.

The loadout dialog lets an operator point a run at their own model subscription. That
choice is worth nothing unless it survives the whole path from run creation to the SDK
client: run creation refuses a provider that could never generate, task creation stamps
the run's provider onto every task it queues, and the executor binds the run owner's
decrypted key to the adapter *before* it generates, holding no transaction while it does.

The other half of these tests is what must NOT happen. The key is the operator's, so it
exists in exactly one place — inside the adapter's client — and never in a request, a
task row, a prepared task, or a persisted artifact. Every provider here is a fake; no
test in this file can reach a network.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.registry import build_definition
from aegis_agents.runtime.task_service import AgentTaskService
from aegis_contracts import AgentSessionState, RunV1
from aegis_contracts.agent_runtime import (
    AgentBudgetV1,
    AgentTaskStatus,
    AgentTaskV1,
    CreateAgentTaskRequestV1,
)
from aegis_contracts.entities import AgentRole, RunLoadoutV1
from aegis_contracts.generation import (
    GenerationMessageRole,
    GenerationMessageV1,
    GenerationRequestV1,
    GenerationResponseV1,
    ModelConfigV1,
    ProviderCapabilitiesV1,
    ProviderCapability,
    ProviderFinishReason,
    ProviderGenerateResponseV1,
    ProviderUsageV1,
)
from aegis_contracts.versioning import (
    AGENT_BUDGET_SCHEMA_VERSION,
    AGENT_TASK_SCHEMA_VERSION,
    CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
    GENERATION_REQUEST_SCHEMA_VERSION,
    GENERATION_RESPONSE_SCHEMA_VERSION,
    MODEL_CONFIG_SCHEMA_VERSION,
    PROVIDER_CAPABILITIES_SCHEMA_VERSION,
    PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION,
    PROVIDER_USAGE_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
)
from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.persistence import InMemoryGenerationArtifactRepository
from aegis_model_provider.registry import ProviderRegistry
from aegis_model_provider.service import GenerationService
from aegis_simulation.run_command_service import RunCommandService
from aegis_simulation_domain import SimulationError, SimulationErrorCode

_RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_OWNER = "user:usr_operator_alpha"
_NOW = datetime(2026, 8, 6, 9, 0, tzinfo=UTC)

#: Stand-in for a real subscription key. Distinctive on purpose: several tests assert it
#: is absent from a serialized payload, and a generic value could match by accident.
_SECRET_KEY = "sk-fake-KEYMATERIAL-must-never-be-persisted"


def _runtime_id(prefix: str, index: int = 1) -> str:
    return f"{prefix}_{index:026d}"


def _run(
    *,
    provider_id: str | None = None,
    model_id: str | None = None,
    owner_user_id: str | None = _OWNER,
) -> RunV1:
    loadout = (
        RunLoadoutV1(provider_id=provider_id, model_id=model_id)
        if provider_id is not None or model_id is not None
        else None
    )
    return RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id=_RUN_ID,
        scenario_version_id="scenario-version:test-v1",
        seed=42,
        status="running",
        started_at=_NOW,
        sim_time=_NOW,
        revision=1,
        owner_user_id=owner_user_id,
        loadout=loadout,
    )


# --- agent definitions carry the run's real model id -------------------------


def test_a_pinned_model_id_replaces_the_synthetic_one() -> None:
    definition = build_definition(
        AgentRole.TRACE, provider_id="openrouter", model_id="anthropic/claude-sonnet-4"
    )
    assert definition.provider_id == "openrouter"
    assert definition.model_id == "anthropic/claude-sonnet-4"


def test_an_unpinned_definition_keeps_the_synthetic_model_id() -> None:
    """Unchanged for every run launched before the loadout could pin a model."""
    assert build_definition(AgentRole.TRACE, provider_id="mock").model_id == "mock-v1"


# --- task creation stamps the run's provider onto the task -------------------


class _FakeTaskRepo:
    def __init__(self) -> None:
        self.added: list[AgentTaskV1] = []

    async def get_by_idempotency(self, *, session_id: str, idempotency_key: str) -> None:
        return None

    async def add(self, task: AgentTaskV1) -> AgentTaskV1:
        self.added.append(task)
        return task


class _FakeRunRepo:
    def __init__(self, run: RunV1 | None) -> None:
        self._run = run

    async def get_by_id(self, _run_id: str) -> RunV1 | None:
        return self._run


class _FakeCredentialRepo:
    """The credential repository seam, scripted per test.

    ``stored`` maps ``(user_id, provider)`` to a plaintext key; ``raises`` lets a test
    reproduce a deployment whose encryption key cannot read the stored ciphertext.
    """

    def __init__(
        self,
        stored: dict[tuple[str, str], str] | None = None,
        *,
        raises: Exception | None = None,
    ) -> None:
        self._stored = stored or {}
        self._raises = raises
        self.decrypt_calls: list[tuple[str, str]] = []
        self.get_calls: list[tuple[str, str]] = []

    async def get(self, user_id: str, provider: str) -> object | None:
        self.get_calls.append((user_id, provider))
        return object() if (user_id, provider) in self._stored else None

    async def get_decrypted_api_key(
        self, user_id: str, provider: str, *, encryption_key: str
    ) -> str | None:
        self.decrypt_calls.append((user_id, provider))
        if self._raises is not None:
            raise self._raises
        return self._stored.get((user_id, provider))


class _TaskServiceUow:
    def __init__(self, run: RunV1 | None) -> None:
        self.runs = _FakeRunRepo(run)
        self.agent_tasks = _FakeTaskRepo()


class _SessionStub:
    id = "agent-session:ags_0001"
    run_id = _RUN_ID
    incident_id = None
    trace_id = _runtime_id("trc")
    role = AgentRole.TRACE
    # Already GATHERING, as a run-scoped lane on its second turn is, so the prepare
    # phase needs no state transition and these tests stay on the provider seam.
    state = AgentSessionState.GATHERING


def _create_task_request(provider_id: str | None = None) -> CreateAgentTaskRequestV1:
    return CreateAgentTaskRequestV1(
        schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
        idempotency_key="idem-1",
        provider_id=provider_id,
    )


@pytest.fixture
def pinned_default(monkeypatch: pytest.MonkeyPatch) -> str:
    """Pin the deployment default so these tests do not read the machine's .env."""
    monkeypatch.setattr(
        "aegis_agents.runtime.task_service._configured_default_provider_id",
        lambda: "openai-compatible",
    )
    return "openai-compatible"


@pytest.mark.asyncio
async def test_a_task_inherits_the_provider_its_run_pinned(pinned_default: str) -> None:
    uow = _TaskServiceUow(_run(provider_id="openrouter", model_id="x-ai/grok-4"))
    task = await AgentTaskService().create_task(
        uow,  # type: ignore[arg-type]
        session=_SessionStub(),  # type: ignore[arg-type]
        request=_create_task_request(),
    )
    assert task.provider_id == "openrouter"


@pytest.mark.asyncio
async def test_an_unpinned_run_still_uses_the_deployment_default(pinned_default: str) -> None:
    uow = _TaskServiceUow(_run())
    task = await AgentTaskService().create_task(
        uow,  # type: ignore[arg-type]
        session=_SessionStub(),  # type: ignore[arg-type]
        request=_create_task_request(),
    )
    assert task.provider_id == pinned_default


@pytest.mark.asyncio
async def test_the_runs_pinned_provider_outranks_one_named_in_the_request(
    pinned_default: str,
) -> None:
    """A request cannot spend a provider the run was never validated against.

    Run creation is where a cloud provider is checked for a stored credential. If a
    per-request ``providerId`` could override the run's, that check would be bypassable
    by anyone who can task an agent, so the run's choice is the authority.
    """
    uow = _TaskServiceUow(_run(provider_id="openai", model_id="gpt-4o"))
    task = await AgentTaskService().create_task(
        uow,  # type: ignore[arg-type]
        session=_SessionStub(),  # type: ignore[arg-type]
        request=_create_task_request(provider_id="mock"),
    )
    assert task.provider_id == "openai"


# --- run creation refuses a provider that could never generate ---------------


class _RunCreationUow:
    def __init__(self, credentials: _FakeCredentialRepo) -> None:
        self.provider_credentials = credentials


async def _create_run(
    loadout: RunLoadoutV1 | None,
    *,
    credentials: _FakeCredentialRepo,
    owner_user_id: str | None = _OWNER,
) -> None:
    from pathlib import Path

    from aegis_contracts import RunCreateRequestV1
    from aegis_contracts.versioning import RUN_CREATE_REQUEST_SCHEMA_VERSION

    service = RunCommandService(Path.cwd())
    await service.create_run(
        _RunCreationUow(credentials),  # type: ignore[arg-type]
        RunCreateRequestV1(
            schema_version=RUN_CREATE_REQUEST_SCHEMA_VERSION,
            scenario_package_path="scenarios/_does-not-exist",
            loadout=loadout,
        ),
        owner_user_id=owner_user_id,
    )


@pytest.mark.asyncio
async def test_an_unknown_provider_id_is_refused_at_launch() -> None:
    with pytest.raises(SimulationError) as exc:
        await _create_run(
            RunLoadoutV1(provider_id="definitely-not-a-provider"),
            credentials=_FakeCredentialRepo(),
        )
    assert exc.value.code == SimulationErrorCode.VALIDATION_FAILED
    assert "definitely-not-a-provider" in exc.value.message


@pytest.mark.asyncio
async def test_a_cloud_provider_without_a_connected_key_is_refused_at_launch() -> None:
    credentials = _FakeCredentialRepo()
    with pytest.raises(SimulationError) as exc:
        await _create_run(
            RunLoadoutV1(provider_id="openai", model_id="gpt-4o"), credentials=credentials
        )
    assert exc.value.code == SimulationErrorCode.VALIDATION_FAILED
    # Actionable: it must say what to do, not merely that something is missing.
    assert "Connect" in exc.value.message
    assert credentials.get_calls == [(_OWNER, "openai")]


@pytest.mark.asyncio
@pytest.mark.parametrize("model_id", [None, "   "])
async def test_a_cloud_provider_pinned_without_a_model_is_refused_at_launch(
    model_id: str | None,
) -> None:
    """A key with no model spends the operator's own subscription on a model nobody chose.

    OpenAI is the silent case: with no model pinned the adapter falls back to the
    deployment's ``AEGIS_PROVIDER_OPENAI_MODEL``, so the run looks healthy while billing
    the operator for something they never picked. Refuse at the launch, before the
    credential lookup — this needs no I/O to decide.
    """
    credentials = _FakeCredentialRepo({(_OWNER, "openai"): _SECRET_KEY})
    with pytest.raises(SimulationError) as exc:
        await _create_run(
            RunLoadoutV1(provider_id="openai", model_id=model_id), credentials=credentials
        )
    assert exc.value.code == SimulationErrorCode.VALIDATION_FAILED
    assert "model" in exc.value.message.lower()
    assert credentials.get_calls == []


@pytest.mark.asyncio
async def test_a_cloud_provider_with_a_connected_key_passes_validation() -> None:
    """Validation clears, so the launch proceeds and fails on the next step instead."""
    credentials = _FakeCredentialRepo({(_OWNER, "openai"): _SECRET_KEY})
    with pytest.raises(SimulationError) as exc:
        await _create_run(
            RunLoadoutV1(provider_id="openai", model_id="gpt-4o"), credentials=credentials
        )
    assert "Scenario package not found" in exc.value.message


@pytest.mark.asyncio
async def test_the_local_provider_needs_no_credential() -> None:
    credentials = _FakeCredentialRepo()
    with pytest.raises(SimulationError) as exc:
        await _create_run(
            RunLoadoutV1(provider_id="openai-compatible"), credentials=credentials
        )
    assert "Scenario package not found" in exc.value.message
    assert credentials.get_calls == []


@pytest.mark.asyncio
async def test_a_run_with_no_pinned_provider_is_never_asked_about_credentials() -> None:
    credentials = _FakeCredentialRepo()
    with pytest.raises(SimulationError) as exc:
        await _create_run(None, credentials=credentials)
    assert "Scenario package not found" in exc.value.message
    assert credentials.get_calls == []


# --- the executor binds the owner's key to the adapter, and nothing else -----


class _StubProvider:
    """A provider fake that holds a key exactly as a real adapter does."""

    provider_id = "openai"

    def __init__(self, api_key: str | None = None, model_id: str | None = None) -> None:
        self.api_key = api_key
        self.model_id = model_id

    def capabilities(self) -> ProviderCapabilitiesV1:
        return ProviderCapabilitiesV1(
            schema_version=PROVIDER_CAPABILITIES_SCHEMA_VERSION,
            capabilities=[ProviderCapability.STRUCTURED_OUTPUT, ProviderCapability.TOOLS],
        )

    async def generate(self, request: GenerationRequestV1) -> GenerationResponseV1:
        return GenerationResponseV1(
            schema_version=GENERATION_RESPONSE_SCHEMA_VERSION,
            request_id=request.request_id,
            trace_id=request.trace_id,
            provider_id=self.provider_id,
            model_id=self.model_id or "gpt-4o",
            prompt_version=request.model_config_ref.prompt_version,
            content=json.dumps({"rationale": "quiet"}),
            structured_data={"rationale": "quiet"},
            finish_reason=ProviderFinishReason.STOP,
            usage=ProviderUsageV1(
                schema_version=PROVIDER_USAGE_SCHEMA_VERSION,
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
            ),
            latency_ms=1,
            completed_at=_NOW,
        )


class _RecordingGeneration:
    """The generation facade seam: records what was bound and how it was called."""

    def __init__(self) -> None:
        self.bindings: list[tuple[str, str | None, str | None]] = []
        self.calls: list[tuple[GenerationRequestV1, Any]] = []
        self.open_writes_at_call: list[int] = []
        self.uow: Any = None

    def bind_provider(
        self, provider_id: str, *, api_key: str | None = None, model_id: str | None = None
    ) -> _StubProvider:
        self.bindings.append((provider_id, api_key, model_id))
        return _StubProvider(api_key=api_key, model_id=model_id)

    async def generate(
        self, request: GenerationRequestV1, *, provider: Any = None
    ) -> ProviderGenerateResponseV1:
        self.calls.append((request, provider))
        if self.uow is not None:
            self.open_writes_at_call.append(self.uow.open_writes)
        return ProviderGenerateResponseV1(
            schema_version=PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION,
            response=await _StubProvider().generate(request),
        )


class _EmptyRepo:
    async def list_by_run(self, _run_id: str, *, limit: int = 10_000) -> list[Any]:
        return []

    async def list_for_run(self, _run_id: str) -> list[Any]:
        return []

    async def list_for_session(self, _session_id: str) -> list[Any]:
        return []

    async def next_sequence(self, _run_id: str) -> int:
        return 1

    async def get_by_id(self, _id: str) -> Any:
        return None


class _AgentTaskRepo:
    def __init__(self, task: AgentTaskV1) -> None:
        self.task = task

    async def get_by_id(self, _task_id: str) -> AgentTaskV1:
        return self.task

    async def claim_transition(self, task: AgentTaskV1, *, from_statuses: tuple[str, ...]) -> bool:
        self.task = task
        return True

    async def list_for_session(self, _session_id: str) -> list[AgentTaskV1]:
        return []


class _AgentSessionRepo:
    async def get_by_id(self, _session_id: str) -> _SessionStub:
        return _SessionStub()

    async def get_budget(self, _session_id: str) -> AgentBudgetV1:
        return AgentBudgetV1(
            schema_version=AGENT_BUDGET_SCHEMA_VERSION,
            max_tokens=8000,
            max_latency_ms=60_000,
            max_cost_usd=1.0,
        )


class _SessionLike:
    def expire_all(self) -> None:
        return None


class _ExecutorUow:
    """The slice of the unit of work ``_claim_and_prepare`` touches."""

    def __init__(self, task: AgentTaskV1, run: RunV1, credentials: _FakeCredentialRepo) -> None:
        self.session = _SessionLike()
        self.agent_tasks = _AgentTaskRepo(task)
        self.agent_sessions = _AgentSessionRepo()
        self.runs = _FakeRunRepo(run)
        self.provider_credentials = credentials
        self.alerts = _EmptyRepo()
        self.incidents = _EmptyRepo()
        self.evidence = _EmptyRepo()
        self.events = _EmptyRepo()
        self.agent_artifacts = _EmptyRepo()
        self.tool_invocations = _EmptyRepo()
        self.open_writes = 0
        self.commits = 0
        self.failed_tasks: list[AgentTaskV1] = []

    async def append_event(self, envelope: Any) -> Any:
        self.open_writes += 1
        return envelope

    async def commit(self) -> None:
        self.commits += 1
        self.open_writes = 0

    async def rollback(self) -> None:
        self.open_writes = 0


def _queued_task(provider_id: str) -> AgentTaskV1:
    return AgentTaskV1(
        schema_version=AGENT_TASK_SCHEMA_VERSION,
        id=_runtime_id("atk"),
        session_id=_SessionStub.id,
        run_id=_RUN_ID,
        incident_id=None,
        status=AgentTaskStatus.QUEUED,
        attempt=1,
        idempotency_key="initial",
        trace_id=_runtime_id("trc"),
        provider_id=provider_id,
        created_at=_NOW,
        updated_at=_NOW,
    )


async def _prepare(
    *,
    provider_id: str | None,
    model_id: str | None,
    credentials: _FakeCredentialRepo,
    monkeypatch: pytest.MonkeyPatch,
    task_provider_id: str | None = None,
    encryption_key: str | None = "deployment-key",
    owner_user_id: str | None = _OWNER,
) -> tuple[Any, _RecordingGeneration, _ExecutorUow]:
    """Prepare one task. ``provider_id``/``model_id`` are the RUN's loadout pin.

    ``task_provider_id`` defaults to the pinned provider, which is what task creation
    produces. Passing it separately is how a test reproduces a task whose provider came
    from somewhere other than the loadout — the deployment default, or a caller.
    """
    monkeypatch.setattr(
        "aegis_agents.runtime.executor._deployment_encryption_key", lambda: encryption_key
    )
    generation = _RecordingGeneration()
    executor = TaskExecutor(generation=generation)  # type: ignore[arg-type]
    task = _queued_task(task_provider_id or provider_id or "mock")
    run = _run(provider_id=provider_id, model_id=model_id, owner_user_id=owner_user_id)
    uow = _ExecutorUow(task, run, credentials)
    generation.uow = uow
    prepared = await executor._claim_and_prepare(uow, task.id)  # type: ignore[arg-type]
    return prepared, generation, uow


@pytest.mark.asyncio
async def test_the_owners_key_is_decrypted_before_the_task_generates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credentials = _FakeCredentialRepo({(_OWNER, "openai"): _SECRET_KEY})
    prepared, generation, uow = await _prepare(
        provider_id="openai",
        model_id="gpt-4o",
        credentials=credentials,
        monkeypatch=monkeypatch,
    )
    assert credentials.decrypt_calls == [(_OWNER, "openai")]
    # Bound to the adapter, with the run's model, and to nothing else.
    assert generation.bindings == [("openai", _SECRET_KEY, "gpt-4o")]
    assert prepared.provider is not None
    assert prepared.definition.model_id == "gpt-4o"
    # The prepare phase committed, so the model call that follows holds no transaction
    # and therefore no per-run advisory lock.
    assert uow.commits == 1
    assert uow.open_writes == 0


@pytest.mark.asyncio
async def test_the_decrypted_key_never_reaches_the_prepared_task_or_its_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared, _generation, _uow = await _prepare(
        provider_id="openai",
        model_id="gpt-4o",
        credentials=_FakeCredentialRepo({(_OWNER, "openai"): _SECRET_KEY}),
        monkeypatch=monkeypatch,
    )
    assert _SECRET_KEY not in prepared.request.model_dump_json(by_alias=True)
    assert _SECRET_KEY not in repr(prepared.task)
    assert _SECRET_KEY not in repr(prepared.definition)


@pytest.mark.asyncio
async def test_generation_runs_through_the_bound_provider_with_no_transaction_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared, generation, uow = await _prepare(
        provider_id="openai",
        model_id="gpt-4o",
        credentials=_FakeCredentialRepo({(_OWNER, "openai"): _SECRET_KEY}),
        monkeypatch=monkeypatch,
    )
    executor = TaskExecutor(generation=generation)  # type: ignore[arg-type]
    await executor._run_tool_loop(uow, prepared)  # type: ignore[arg-type]
    _request, provider = generation.calls[-1]
    assert getattr(provider, "api_key", None) == _SECRET_KEY
    assert generation.open_writes_at_call == [0]


@pytest.mark.asyncio
async def test_an_unpinned_run_calls_generation_exactly_as_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No provider override, no credential lookup: the default path is untouched."""
    credentials = _FakeCredentialRepo()
    prepared, generation, uow = await _prepare(
        provider_id="openai-compatible",
        model_id=None,
        credentials=credentials,
        monkeypatch=monkeypatch,
    )
    assert credentials.decrypt_calls == []
    assert generation.bindings == []
    assert prepared.provider is None
    executor = TaskExecutor(generation=generation)  # type: ignore[arg-type]
    await executor._run_tool_loop(uow, prepared)  # type: ignore[arg-type]
    assert [provider for _request, provider in generation.calls] == [None]


@pytest.mark.parametrize(
    ("origin", "deployment_default", "requested_provider_id"),
    [
        # A deployment that points AEGIS_PROVIDER_DEFAULT at a cloud endpoint and pays
        # for it with AEGIS_PROVIDER_OPENAI_API_KEY. Every task on every run is "openai".
        pytest.param("deployment-default", "openai", None, id="deployment-default"),
        # A caller naming a provider on the task request — the harness scripts' shape.
        pytest.param("caller-supplied", "mock", "openai", id="caller-supplied"),
    ],
)
@pytest.mark.asyncio
async def test_a_cloud_provider_the_run_did_not_pin_is_served_from_the_environment(
    origin: str,
    deployment_default: str,
    requested_provider_id: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cloud provider id is not by itself a claim on someone's subscription.

    Only a loadout the operator filled in is. A run that pinned nothing is running on
    whatever the deployment configured, and the registry has always served that from the
    environment key — so demanding a per-user credential here would fail every task in
    such a deployment. The task is built through the real task service so the two ways a
    cloud provider reaches an unpinned run are exercised end to end, not assumed.
    """
    monkeypatch.setattr(
        "aegis_agents.runtime.task_service._configured_default_provider_id",
        lambda: deployment_default,
    )
    created = await AgentTaskService().create_task(
        _TaskServiceUow(_run()),  # type: ignore[arg-type]
        session=_SessionStub(),  # type: ignore[arg-type]
        request=_create_task_request(requested_provider_id),
    )
    assert created.provider_id == "openai"

    credentials = _FakeCredentialRepo()
    prepared, generation, uow = await _prepare(
        provider_id=None,
        model_id=None,
        task_provider_id=created.provider_id,
        credentials=credentials,
        monkeypatch=monkeypatch,
    )
    assert credentials.decrypt_calls == []
    assert generation.bindings == []
    assert prepared.provider is None
    # Synthetic model id, so the adapter falls back to its configured model as before.
    assert prepared.definition.model_id == "openai-v1"

    executor = TaskExecutor(generation=generation)  # type: ignore[arg-type]
    await executor._run_tool_loop(uow, prepared)  # type: ignore[arg-type]
    assert [provider for _request, provider in generation.calls] == [None]


@pytest.mark.asyncio
async def test_a_credential_is_still_demanded_when_the_run_did_pin_the_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The counterpart: the same provider id, pinned, still spends the owner's key."""
    credentials = _FakeCredentialRepo({(_OWNER, "openai"): _SECRET_KEY})
    prepared, generation, _uow = await _prepare(
        provider_id="openai",
        model_id="gpt-4o",
        credentials=credentials,
        monkeypatch=monkeypatch,
    )
    assert credentials.decrypt_calls == [(_OWNER, "openai")]
    assert generation.bindings == [("openai", _SECRET_KEY, "gpt-4o")]
    assert prepared.provider is not None


@pytest.mark.asyncio
async def test_a_revoked_credential_fails_the_task_visibly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(AgentRuntimeError) as exc:
        await _prepare(
            provider_id="openai",
            model_id="gpt-4o",
            credentials=_FakeCredentialRepo(),
            monkeypatch=monkeypatch,
        )
    assert exc.value.code == AgentRuntimeErrorCode.PROVIDER_FAILURE
    assert "openai" in exc.value.message


@pytest.mark.parametrize(
    "failure",
    [
        # A rotated or tampered row. The parent class matters more than either child:
        # catching only this one leaves the other unhandled.
        pytest.param("decrypt", id="rotated-encryption-key"),
        # A deployment whose AEGIS_CREDENTIAL_ENCRYPTION_KEY is not a Fernet key at all.
        pytest.param("key", id="malformed-deployment-key"),
    ],
)
@pytest.mark.asyncio
async def test_a_credential_that_cannot_be_read_fails_the_task_rather_than_crashing(
    failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegis_persistence.credentials import CredentialDecryptError, CredentialKeyError

    error: Exception = (
        CredentialDecryptError("Stored provider credential could not be decrypted")
        if failure == "decrypt"
        else CredentialKeyError("AEGIS_CREDENTIAL_ENCRYPTION_KEY is not a valid Fernet key")
    )
    with pytest.raises(AgentRuntimeError) as exc:
        await _prepare(
            provider_id="openai",
            model_id="gpt-4o",
            credentials=_FakeCredentialRepo(raises=error),
            monkeypatch=monkeypatch,
        )
    assert exc.value.code == AgentRuntimeErrorCode.PROVIDER_FAILURE


@pytest.mark.asyncio
async def test_a_deployment_with_no_encryption_key_fails_the_task_visibly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(AgentRuntimeError) as exc:
        await _prepare(
            provider_id="openai",
            model_id="gpt-4o",
            credentials=_FakeCredentialRepo({(_OWNER, "openai"): _SECRET_KEY}),
            monkeypatch=monkeypatch,
            encryption_key=None,
        )
    assert exc.value.code == AgentRuntimeErrorCode.PROVIDER_FAILURE
    assert "AEGIS_CREDENTIAL_ENCRYPTION_KEY" in exc.value.message


# --- nothing that persists ever carries key material -------------------------


def _generation_request() -> GenerationRequestV1:
    return GenerationRequestV1(
        schema_version=GENERATION_REQUEST_SCHEMA_VERSION,
        request_id=_runtime_id("gen"),
        trace_id=_runtime_id("trc"),
        provider_id="openai",
        model_config_ref=ModelConfigV1(
            schema_version=MODEL_CONFIG_SCHEMA_VERSION,
            provider_id="openai",
            model_id="gpt-4o",
            prompt_version="phase19-v1",
        ),
        messages=[
            GenerationMessageV1(role=GenerationMessageRole.USER, content="Summarise the run.")
        ],
    )


@pytest.mark.asyncio
async def test_the_persisted_artifact_contains_no_key_material() -> None:
    """The artifact is the durable record of a call; the key must not be in it."""
    artifacts = InMemoryGenerationArtifactRepository()
    service = GenerationService(
        registry=ProviderRegistry({}, default_provider_id="openai"),
        settings=ProviderSettings(),
        artifact_repository=artifacts,
    )
    request = _generation_request()
    response = await service.generate(request, provider=_StubProvider(api_key=_SECRET_KEY))
    assert response.error is None

    artifact = await artifacts.get_by_request_id(request.request_id)
    assert artifact is not None
    assert _SECRET_KEY not in artifact.model_dump_json(by_alias=True)
    assert _SECRET_KEY not in request.model_dump_json(by_alias=True)


@pytest.mark.asyncio
async def test_a_bound_provider_still_has_its_capabilities_checked() -> None:
    """The override bypasses ``resolve``; it must not bypass the capability gate."""

    class _NoStructuredOutput(_StubProvider):
        def capabilities(self) -> ProviderCapabilitiesV1:
            return ProviderCapabilitiesV1(
                schema_version=PROVIDER_CAPABILITIES_SCHEMA_VERSION,
                capabilities=[ProviderCapability.TOOLS],
            )

    service = GenerationService(
        registry=ProviderRegistry({}, default_provider_id="openai"),
        settings=ProviderSettings(),
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )
    request = _generation_request().model_copy(
        update={"capabilities_required": [ProviderCapability.STRUCTURED_OUTPUT]}
    )
    response = await service.generate(request, provider=_NoStructuredOutput())
    assert response.error is not None
    assert response.error.code.value == "CAPABILITY_UNSUPPORTED"

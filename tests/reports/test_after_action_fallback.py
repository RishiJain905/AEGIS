"""Deterministic after-action report fallback.

A stopped run must always end with a usable report. When the agents never produced
WATCHTOWER / ORACLE / BASTION artifacts — an unattended run, or one whose model provider
was unavailable — the report is assembled from persisted run state instead, and is
labelled ``generation_mode = deterministic`` so it never reads as agent-authored.

Fully offline: the unit of work is faked, so no PostgreSQL and no model provider is
touched (core CI must pass without an external LLM).
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from aegis_agents.roles.scribe.coordinator import (
    ScribeCoordinator,
    ScribeReportOutcome,
)
from aegis_contracts.entities import IncidentState, IncidentV1
from aegis_contracts.investigation import InvestigationDetailV1, WatchtowerTriageResultV1
from aegis_contracts.reports import (
    AfterActionReportV1,
    ReportExportArtifactV1,
    ReportGenerationModeV1,
    ReportGenerationStatusV1,
    ReportVersionV1,
    TriggerScribeRequestV1,
)
from aegis_contracts.versioning import (
    INCIDENT_SCHEMA_VERSION,
    INVESTIGATION_DETAIL_SCHEMA_VERSION,
    TRIGGER_SCRIBE_REQUEST_SCHEMA_VERSION,
)

RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
INCIDENT_ID = "incident:inc_001"
TRACE_ID = "trc_01ARZ3NDEKTSV4RRFFQ69G5FB1"


class _FakeIncidents:
    def __init__(self, incidents: list[IncidentV1]) -> None:
        self._incidents = incidents

    async def list_by_run(self, run_id: str) -> list[IncidentV1]:
        return [item for item in self._incidents if item.run_id == run_id]

    async def get_by_id(self, incident_id: str) -> IncidentV1 | None:
        return next((item for item in self._incidents if item.id == incident_id), None)


class _FakeInvestigation:
    def __init__(self, detail: InvestigationDetailV1) -> None:
        self._detail = detail

    async def get_detail(self, incident_id: str, run_id: str) -> InvestigationDetailV1:
        return self._detail


class _FakeEvents:
    def __init__(self) -> None:
        self.appended: list[Any] = []
        self._sequence = 0

    async def list_by_run(self, run_id: str, limit: int = 0) -> list[Any]:
        return []

    async def next_sequence(self, run_id: str) -> int:
        self._sequence += 1
        return self._sequence


class _FakeAlerts:
    async def list_by_run(self, run_id: str) -> list[Any]:
        return []


class _FakeObjects:
    def __init__(self) -> None:
        self.added: list[Any] = []

    async def add(self, reference: Any) -> Any:
        self.added.append(reference)
        return reference


class _FakeReports:
    """In-memory stand-in for the report repository, shared across uow instances."""

    def __init__(self) -> None:
        self.versions: list[ReportVersionV1] = []
        self.reports: list[AfterActionReportV1] = []
        self.exports: list[ReportExportArtifactV1] = []

    async def latest_version_number(self, run_id: str) -> int:
        return max(
            (item.version_number for item in self.versions if item.run_id == run_id),
            default=0,
        )

    async def add_version(
        self,
        version: ReportVersionV1,
        report: AfterActionReportV1,
    ) -> ReportVersionV1:
        self.versions.append(version)
        self.reports.append(report)
        return version

    async def list_versions(self, run_id: str) -> list[ReportVersionV1]:
        return [item for item in self.versions if item.run_id == run_id]

    async def add_export(
        self,
        artifact: ReportExportArtifactV1,
        *,
        content: bytes,
    ) -> ReportExportArtifactV1:
        self.exports.append(artifact)
        return artifact


class _FakeUow:
    def __init__(
        self,
        *,
        incidents: list[IncidentV1],
        detail: InvestigationDetailV1,
        reports: _FakeReports,
    ) -> None:
        self.incidents = _FakeIncidents(incidents)
        self.investigation = _FakeInvestigation(detail)
        self.events = _FakeEvents()
        self.alerts = _FakeAlerts()
        self.objects = _FakeObjects()
        self.reports = reports
        self.appended_events: list[Any] = []

    async def append_event(self, event: Any) -> Any:
        self.appended_events.append(event)
        return event


def _incident() -> IncidentV1:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    return IncidentV1(
        schema_version=INCIDENT_SCHEMA_VERSION,
        id=INCIDENT_ID,
        run_id=RUN_ID,
        title="Suspicious relay beaconing",
        state=IncidentState.OPEN,
        alert_ids=[],
        created_at=now,
        updated_at=now,
        revision=1,
    )


def _empty_detail() -> InvestigationDetailV1:
    """What a run whose agents never ran actually looks like."""
    return InvestigationDetailV1(
        schema_version=INVESTIGATION_DETAIL_SCHEMA_VERSION,
        incident_id=INCIDENT_ID,
        run_id=RUN_ID,
    )


def _request() -> TriggerScribeRequestV1:
    return TriggerScribeRequestV1(
        schema_version=TRIGGER_SCRIBE_REQUEST_SCHEMA_VERSION,
        run_id=RUN_ID,
        incident_id=None,
        trace_id=TRACE_ID,
        idempotency_key=f"auto-scribe-{RUN_ID}",
    )


def _uow(
    *,
    incidents: list[IncidentV1] | None = None,
    detail: InvestigationDetailV1 | None = None,
    reports: _FakeReports | None = None,
) -> _FakeUow:
    return _FakeUow(
        incidents=[_incident()] if incidents is None else incidents,
        detail=detail or _empty_detail(),
        reports=reports or _FakeReports(),
    )


@pytest.mark.asyncio
async def test_run_without_agent_artifacts_still_gets_a_report() -> None:
    reports = _FakeReports()
    uow = _uow(reports=reports)

    result = await ScribeCoordinator().ensure_report_for_run(uow, _request())  # type: ignore[arg-type]

    assert result.outcome is ScribeReportOutcome.DETERMINISTIC
    assert len(reports.versions) == 1
    version = reports.versions[0]
    report = reports.reports[0]
    # Labelled as machine-assembled, with no model provenance attached.
    assert version.generation_mode is ReportGenerationModeV1.DETERMINISTIC
    assert version.status is ReportGenerationStatusV1.COMPLETED
    assert report.generation_mode is ReportGenerationModeV1.DETERMINISTIC
    assert report.narrative_provider_id is None
    assert report.session_id is None
    assert report.task_id is None
    # ...and it says so in prose too, because the exports travel outside the UI.
    assert "No agent investigation artifacts were recorded" in report.executive_summary
    # Exports exist so /reports has something to link to.
    assert {item.format.value for item in reports.exports} == {"markdown", "json", "html"}


@pytest.mark.asyncio
async def test_deterministic_report_is_reproducible_from_the_same_run_state() -> None:
    first = _uow()
    second = _uow()

    await ScribeCoordinator().ensure_report_for_run(first, _request())  # type: ignore[arg-type]
    await ScribeCoordinator().ensure_report_for_run(second, _request())  # type: ignore[arg-type]

    # Same run state, independent generations: identical content checksum (report ids and
    # timestamps differ, which is why the checksum must not cover them).
    assert first.reports.reports[0].checksum == second.reports.reports[0].checksum
    assert first.reports.reports[0].id != second.reports.reports[0].id


@pytest.mark.asyncio
async def test_refinalizing_does_not_create_a_second_report_version() -> None:
    reports = _FakeReports()

    await ScribeCoordinator().ensure_report_for_run(_uow(reports=reports), _request())  # type: ignore[arg-type]
    second = await ScribeCoordinator().ensure_report_for_run(
        _uow(reports=reports),  # type: ignore[arg-type]
        _request(),
    )

    assert second.outcome is ScribeReportOutcome.ALREADY_REPORTED
    assert second.report_version_id == reports.versions[0].id
    assert len(reports.versions) == 1


@pytest.mark.asyncio
async def test_run_without_incidents_is_skipped_rather_than_failing() -> None:
    reports = _FakeReports()
    uow = _uow(incidents=[], reports=reports)

    result = await ScribeCoordinator().ensure_report_for_run(uow, _request())  # type: ignore[arg-type]

    assert result.outcome is ScribeReportOutcome.SKIPPED_NO_INCIDENT
    assert reports.versions == []


@pytest.mark.asyncio
async def test_full_investigation_still_takes_the_strict_agent_path() -> None:
    """The LLM path is unchanged when the prerequisites hold — no silent downgrade."""
    detail = _empty_detail().model_copy(
        update={
            "triage_results": [object()],
            "hypotheses": [object()],
            "proposals": [object()],
        }
    )
    reports = _FakeReports()
    uow = _uow(detail=detail, reports=reports)

    delegated: list[str] = []

    class _StrictOnlyCoordinator(ScribeCoordinator):
        async def trigger_for_run(self, uow: object, request: object) -> Any:  # type: ignore[override]
            delegated.append("strict")
            from aegis_agents.roles.scribe.coordinator import ScribeTriggerResult

            return ScribeTriggerResult(
                incident_id=INCIDENT_ID,
                scribe_session_id="ses_stub",
                scribe_task_id="tsk_stub",
            )

    result = await _StrictOnlyCoordinator().ensure_report_for_run(uow, _request())  # type: ignore[arg-type]

    assert delegated == ["strict"]
    assert result.outcome is ScribeReportOutcome.AGENT_TASK_QUEUED
    assert result.scribe_task_id == "tsk_stub"
    # The fallback did not fire: no deterministic report was written behind SCRIBE's back.
    assert reports.versions == []


@pytest.mark.asyncio
async def test_deterministic_safety_net_covers_a_failed_agent_task() -> None:
    """Full investigation + failed SCRIBE run still ends with a report."""
    # Only the attribute the source assembler reads is stubbed; the point of this test is
    # the safety net firing, not the triage payload.
    detail = _empty_detail().model_copy(
        update={"triage_results": [SimpleNamespace(session_id="agent-session:ags_stub")]}
    )
    reports = _FakeReports()
    uow = _uow(detail=detail, reports=reports)

    result = await ScribeCoordinator().ensure_deterministic_report(uow, _request())  # type: ignore[arg-type]

    assert result.outcome is ScribeReportOutcome.DETERMINISTIC
    assert len(reports.versions) == 1
    assert reports.versions[0].generation_mode is ReportGenerationModeV1.DETERMINISTIC


def test_triage_result_contract_is_importable() -> None:
    # Guards the model_copy stubs above from drifting into a contract that no longer exists.
    assert WatchtowerTriageResultV1 is not None

"""SCRIBE acceptance criteria tests."""

from __future__ import annotations

from aegis_agents.roles.registry import get_role_handler
from aegis_agents.roles.scribe.schemas import SCRIBE_NARRATIVE_OUTPUT_SCHEMA
from aegis_contracts.entities import AgentRole
from aegis_contracts.investigation import InvestigationDetailV1
from aegis_contracts.reports import AfterActionReportSourceV1
from aegis_contracts.versioning import (
    AFTER_ACTION_REPORT_SOURCE_SCHEMA_VERSION,
    INVESTIGATION_DETAIL_SCHEMA_VERSION,
)
from aegis_reports.export import checksum_bytes, render_markdown
from aegis_reports.template import build_template_report


def test_scribe_handler_registered_with_phase23_prompt() -> None:
    handler = get_role_handler(AgentRole.SCRIBE)
    assert handler is not None
    assert handler.prompt_version == "phase23-scribe-v1"


def test_scribe_output_schema_requires_claims() -> None:
    assert "claims" in SCRIBE_NARRATIVE_OUTPUT_SCHEMA["required"]


def test_template_report_produces_checksum_and_readable_markdown() -> None:
    source = AfterActionReportSourceV1(
        schema_version=AFTER_ACTION_REPORT_SOURCE_SCHEMA_VERSION,
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        incident_id="incident:inc_001",
        source_sequence_from=1,
        source_sequence_to=3,
        investigation_summary={"incidentTitle": "Test incident", "incidentState": "open"},
    )
    investigation = InvestigationDetailV1(
        schema_version=INVESTIGATION_DETAIL_SCHEMA_VERSION,
        incident_id="incident:inc_001",
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    )
    report = build_template_report(
        report_id="aar_test",
        version_number=1,
        source=source,
        investigation=investigation,
    )
    markdown = render_markdown(report)
    assert "Executive summary" in markdown
    assert len(report.checksum) == 64
    assert checksum_bytes(markdown.encode("utf-8"))

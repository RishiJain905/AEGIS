"""Stored-XSS and traversal attempts against report exports."""

from __future__ import annotations

import pytest
from aegis_contracts.investigation import InvestigationDetailV1
from aegis_contracts.reports import AfterActionReportSourceV1
from aegis_contracts.versioning import (
    AFTER_ACTION_REPORT_SOURCE_SCHEMA_VERSION,
    INVESTIGATION_DETAIL_SCHEMA_VERSION,
)
from aegis_reports.export import load_template, render_html
from aegis_reports.template import build_template_report


def _report_with_untrusted_markup():  # noqa: ANN202
    payload = '<script>alert("stored-xss")</script><img src=x onerror=alert(1)>'
    source = AfterActionReportSourceV1(
        schema_version=AFTER_ACTION_REPORT_SOURCE_SCHEMA_VERSION,
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        incident_id="incident:inc_security_export",
        source_sequence_from=1,
        source_sequence_to=1,
        investigation_summary={"incidentTitle": payload, "incidentState": payload},
    )
    investigation = InvestigationDetailV1(
        schema_version=INVESTIGATION_DETAIL_SCHEMA_VERSION,
        incident_id=source.incident_id,
        run_id=source.run_id,
    )
    report = build_template_report(
        report_id="aar_security_export",
        version_number=1,
        source=source,
        investigation=investigation,
    )
    claim = report.claims[0].model_copy(update={"text": payload})
    return report.model_copy(
        update={
            "title": payload,
            "executive_summary": payload,
            "checksum": payload,
            "claims": [claim],
        }
    )


def test_html_export_escapes_all_report_and_model_originated_fields() -> None:
    rendered = render_html(_report_with_untrusted_markup())

    assert "<script>" not in rendered
    assert "<img src=x" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "&lt;img src=x onerror=alert(1)&gt;" in rendered


@pytest.mark.parametrize(
    "name",
    ["../../.env.example", "../reports/../../.env.example", "C:/Windows/win.ini"],
)
def test_template_loader_rejects_path_traversal_and_absolute_paths(name: str) -> None:
    with pytest.raises(ValueError, match="Invalid report template path"):
        load_template(name)


def test_template_loader_still_reads_a_template_inside_the_allowed_root() -> None:
    assert "report" in load_template("README.md").lower()

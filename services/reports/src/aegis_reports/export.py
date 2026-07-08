"""Export after-action reports to Markdown, JSON, and HTML."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from aegis_contracts.reports import AfterActionReportV1, ReportExportFormatV1
from aegis_contracts.versioning import WORKSPACE_VERSION


def checksum_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def render_markdown(report: AfterActionReportV1) -> str:
    lines = [
        f"# {report.title}",
        "",
        f"**Report version:** {report.version_number}",
        f"**Workspace version:** {WORKSPACE_VERSION}",
        f"**Checksum:** `{report.checksum}`",
        f"**Grounding fallback:** {report.grounding_fallback}",
        "",
        "## Executive summary",
        report.executive_summary,
        "",
        "## Chronology",
        report.chronology_summary,
        "",
        "## Timeline",
    ]
    for entry in report.timeline[:200]:
        lines.append(
            f"- seq {entry.sequence} `{entry.event_id}` ({entry.event_type}): {entry.label}"
        )
    lines.extend(["", "## Claims"])
    for claim in report.claims:
        lines.append(
            f"- [{claim.category.value}] {claim.text}"
            + (f" _(rejected: {claim.rejection_reason})_" if claim.rejection_reason else "")
        )
        for citation in claim.citations:
            lines.append(f"  - citation `{citation.reference_id}` ({citation.kind.value})")
    if report.contradictions:
        lines.extend(["", "## Contradictions"])
        lines.extend(f"- {item}" for item in report.contradictions)
    if report.uncertainties:
        lines.extend(["", "## Uncertainties"])
        lines.extend(f"- {item}" for item in report.uncertainties)
    lines.extend(["", "## Lessons"])
    lines.extend(f"- {item}" for item in report.lessons)
    return "\n".join(lines) + "\n"


def render_html(report: AfterActionReportV1) -> str:
    claim_rows = "\n".join(
        f"<li><strong>{claim.category.value}</strong> {claim.text}</li>"
        for claim in report.claims[:200]
    )
    timeline_rows = "\n".join(
        f"<li>seq {entry.sequence} <code>{entry.event_id}</code> {entry.label}</li>"
        for entry in report.timeline[:200]
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{report.title}</title></head>
<body>
<h1>{report.title}</h1>
<p>Version {report.version_number} · checksum <code>{report.checksum}</code></p>
<h2>Executive summary</h2><p>{report.executive_summary}</p>
<h2>Timeline</h2><ul>{timeline_rows}</ul>
<h2>Claims</h2><ul>{claim_rows}</ul>
</body>
</html>
"""


def render_export(
    report: AfterActionReportV1,
    export_format: ReportExportFormatV1,
) -> tuple[bytes, str]:
    match export_format:
        case ReportExportFormatV1.JSON:
            payload = report.model_dump(by_alias=True, mode="json")
            content = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            return content, "application/json"
        case ReportExportFormatV1.MARKDOWN:
            content = render_markdown(report).encode("utf-8")
            return content, "text/markdown; charset=utf-8"
        case ReportExportFormatV1.HTML:
            content = render_html(report).encode("utf-8")
            return content, "text/html; charset=utf-8"
        case _:
            msg = f"Unsupported export format: {export_format}"
            raise ValueError(msg)


def load_template(name: str) -> str:
    template_path = Path(__file__).resolve().parents[4] / "templates" / "reports" / name
    return template_path.read_text(encoding="utf-8")

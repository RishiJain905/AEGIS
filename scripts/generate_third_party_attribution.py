"""Generate a deterministic third-party attribution document from the CI license report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def render_attribution(report: dict[str, object], source: str) -> str:
    components = report.get("components")
    if not isinstance(components, list):
        raise ValueError("license report must contain a components array")

    rows: list[tuple[str, str, str]] = []
    for component in components:
        if not isinstance(component, dict):
            raise ValueError("license report components must be objects")
        name = str(component.get("name", "")).strip()
        version = str(component.get("version", "")).strip()
        licenses = component.get("licenses", [])
        if isinstance(licenses, list):
            license_text = ", ".join(
                sorted({str(value).strip() for value in licenses if str(value).strip()})
            )
        else:
            license_text = ""
        rows.append((name, version, license_text or "UNKNOWN"))

    rows.sort(key=lambda row: (row[0].lower(), row[1], row[2]))
    lines = [
        "# Third-Party Attribution",
        "",
        "This file is generated from the CI CycloneDX-derived license report. It is an",
        "attribution inventory, not a legal approval or a substitute for reviewing the",
        "license text and obligations for each dependency.",
        "",
        f"Source report: `{source}`",
        "",
        "| Component | Version | Reported license(s) |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {name} | {version} | {license_text} |" for name, version, license_text in rows)
    if not rows:
        lines.extend(["", "The source report contained no components."])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="CI license-report.json")
    parser.add_argument("--output", type=Path, required=True, help="Markdown output path")
    args = parser.parse_args()

    report = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("license report must be a JSON object")
    output = render_attribution(report, args.input.as_posix())
    args.output.write_text(output, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

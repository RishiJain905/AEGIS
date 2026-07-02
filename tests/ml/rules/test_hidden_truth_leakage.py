"""Hidden truth leakage guard."""

from pathlib import Path


def test_detection_modules_do_not_import_expected_evidence() -> None:
    root = Path("services/incidents/src/aegis_incidents")
    for path in root.rglob("*.py"):
        if path.name == "evaluation.py":
            continue
        content = path.read_text(encoding="utf-8")
        assert "expected-evidence" not in content
        assert "expected_evidence" not in content

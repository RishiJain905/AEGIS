"""Ensure evaluation labels are not imported by training/inference runtime."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path


def test_training_modules_do_not_import_evaluation_labels() -> None:
    forbidden = ("SEED_ROOT_CAUSE", "CAUSE_EXPECTED_RULES", "expected-evidence")
    import aegis_ml

    for module_info in pkgutil.walk_packages(aegis_ml.__path__, aegis_ml.__name__ + "."):
        if "evaluation" in module_info.name:
            continue
        module = importlib.import_module(module_info.name)
        source_path = getattr(module, "__file__", "") or ""
        if not source_path.endswith(".py"):
            continue
        text = Path(source_path).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{module_info.name} references forbidden token {token}"

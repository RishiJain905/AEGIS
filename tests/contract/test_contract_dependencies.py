"""Contract package dependency boundary smoke tests."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import aegis_contracts


def test_contracts_package_has_no_apps_imports() -> None:
    forbidden_prefixes = ("aegis_api", "aegis_simulation", "aegis_workers")
    package = importlib.import_module("aegis_contracts")
    for module_info in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        module = importlib.import_module(module_info.name)
        module_path = getattr(module, "__file__", "") or ""
        assert module_path, f"Missing module file for {module_info.name}"
        source = Path(module_path).read_text(encoding="utf-8")
        for prefix in forbidden_prefixes:
            assert prefix not in source, f"{module_info.name} must not reference {prefix}"


def test_public_exports_include_core_contracts() -> None:
    assert "DomainEventEnvelopeV1" in aegis_contracts.__all__
    assert "GraphNodeV1" in aegis_contracts.__all__
    assert "WORKSPACE_VERSION" in aegis_contracts.__all__

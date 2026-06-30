"""Scenario SDK CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aegis_scenario_sdk.diagnostics import ValidationDiagnostic
from aegis_scenario_sdk.packaging.manifest import build_package_manifest, write_package_manifest
from aegis_scenario_sdk.publication import publish_package
from aegis_scenario_sdk.validation.pipeline import validate_package, validate_package_result


def _print_diagnostics(diagnostics: list[ValidationDiagnostic]) -> None:
    for diagnostic in diagnostics:
        print(diagnostic.format_line(), file=sys.stderr)


def cmd_validate(args: argparse.Namespace) -> int:
    result = validate_package_result(
        Path(args.path),
        verify_existing_manifest=not args.skip_package_manifest,
    )
    if result.valid:
        print(f"VALID packageChecksum={result.package_checksum}")
        return 0
    _print_diagnostics(result.diagnostics)
    return 1


def cmd_hash(args: argparse.Namespace) -> int:
    outcome = validate_package(Path(args.path), verify_existing_manifest=False)
    if outcome.manifest is None:
        _print_diagnostics(outcome.diagnostics)
        return 1
    package_manifest = build_package_manifest(outcome.manifest, Path(args.path))
    print(package_manifest.package_checksum)
    return 0


def cmd_package(args: argparse.Namespace) -> int:
    outcome = validate_package(Path(args.path), verify_existing_manifest=False)
    if outcome.manifest is None or outcome.diagnostics:
        _print_diagnostics(outcome.diagnostics)
        return 1
    package_manifest = build_package_manifest(outcome.manifest, Path(args.path))
    output_path = write_package_manifest(Path(args.path), package_manifest)
    print(f"Wrote {output_path}")
    print(f"packageChecksum={package_manifest.package_checksum}")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    output_dir, diagnostics = publish_package(Path(args.path), Path(args.output))
    if diagnostics:
        _print_diagnostics(diagnostics)
        return 1
    print(f"Published to {output_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aegis-scenario")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a scenario package")
    validate_parser.add_argument("path", help="Scenario package directory")
    validate_parser.add_argument(
        "--skip-package-manifest",
        action="store_true",
        help="Skip verification of package.manifest.yaml when present",
    )
    validate_parser.set_defaults(func=cmd_validate)

    hash_parser = subparsers.add_parser("hash", help="Print deterministic package checksum")
    hash_parser.add_argument("path", help="Scenario package directory")
    hash_parser.set_defaults(func=cmd_hash)

    package_parser = subparsers.add_parser("package", help="Build package.manifest.yaml")
    package_parser.add_argument("path", help="Scenario package directory")
    package_parser.set_defaults(func=cmd_package)

    publish_parser = subparsers.add_parser("publish", help="Publish an immutable scenario package")
    publish_parser.add_argument("path", help="Scenario package directory")
    publish_parser.add_argument("--output", required=True, help="Publication output directory")
    publish_parser.set_defaults(func=cmd_publish)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

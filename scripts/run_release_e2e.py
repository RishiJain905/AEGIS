#!/usr/bin/env python3
"""Run the local Playwright release journeys with an explicit browser matrix."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _pnpm_executable() -> str:
    if os.name != "nt":
        return "pnpm"
    local_app_data = os.environ.get("LOCALAPPDATA")
    candidates = []
    if os.environ.get("PNPM_HOME"):
        candidates.append(Path(os.environ["PNPM_HOME"]) / "bin" / "pnpm.CMD")
    if local_app_data:
        candidates.extend(
            [
                Path(local_app_data) / "pnpm" / "bin" / "pnpm.CMD",
                Path(local_app_data) / "corepack-bin" / "pnpm.CMD",
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "pnpm"


def _configure_node_path() -> None:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return
    pnpm_bin = Path(os.environ.get("PNPM_HOME", Path(local_app_data) / "pnpm")) / "bin"
    if (pnpm_bin / "node.exe").exists():
        os.environ["PATH"] = f"{pnpm_bin}{os.pathsep}{os.environ.get('PATH', '')}"


def _system_chromium_path() -> Path | None:
    candidates = [
        os.environ.get("AEGIS_CHROMIUM_EXECUTABLE_PATH", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    return None


def _discover_browsers(repo_root: Path) -> tuple[dict[str, bool], str | None]:
    script = (
        "const fs=require('node:fs');"
        "const p=require('@playwright/test');"
        "for (const [name,browser] of Object.entries({chromium:p.chromium,"
        "firefox:p.firefox,webkit:p.webkit})) "
        "console.log(`${name}=${fs.existsSync(browser.executablePath())}`);"
    )
    try:
        completed = subprocess.run(
            [_pnpm_executable(), "--filter", "@aegis/web", "exec", "node", "-e", script],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return {}, str(exc)
    if completed.returncode != 0:
        return {}, (completed.stderr or completed.stdout or "browser discovery failed").strip()
    found: dict[str, bool] = {}
    for line in completed.stdout.splitlines():
        if "=" not in line:
            continue
        name, value = line.strip().split("=", 1)
        if name in {"chromium", "firefox", "webkit"}:
            found[name] = value.lower() == "true"
    return found, None


def main() -> int:
    _configure_node_path()
    repo_root = _repo_root()
    output_path = Path(
        os.environ.get("AEGIS_RELEASE_REPORT_PATH", "docs/release/evidence/e2e.json")
    )
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    browsers, discovery_error = _discover_browsers(repo_root)
    skipped: list[dict[str, str]] = []
    if discovery_error:
        skipped.extend(
            {"browser": browser, "reason": f"browser discovery failed: {discovery_error}"}
            for browser in ("firefox", "webkit")
        )
        browsers = {"chromium": True}
    else:
        system_chromium = _system_chromium_path()
        if not browsers.get("chromium", False) and system_chromium is not None:
            browsers["chromium"] = True
            os.environ["AEGIS_CHROMIUM_EXECUTABLE_PATH"] = str(system_chromium)
        for browser in ("firefox", "webkit"):
            if not browsers.get(browser, False):
                skipped.append(
                    {
                        "browser": browser,
                        "reason": "Playwright browser executable is not installed locally",
                    }
                )

    if not browsers.get("chromium", False):
        report = {
            "schemaVersion": "aegis.release-e2e/v1",
            "status": "failed",
            "browsers": [],
            "skippedBrowsers": skipped,
            "tests": [],
            "error": "required Chromium executable is not installed locally",
        }
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("E2E ERROR: required Chromium executable is not installed locally")
        print(f"E2E report: {output_path}")
        print("RELEASE E2E: FAIL")
        return 1

    installed = [browser for browser in ("chromium", "firefox", "webkit") if browsers.get(browser)]
    environment = os.environ.copy()
    system_chromium = _system_chromium_path()
    environment.update(
        {
            "AEGIS_RELEASE_REPORT_PATH": str(output_path),
            "AEGIS_BROWSER_PROJECTS": ",".join(installed),
            "AEGIS_BROWSER_SKIP_REASONS": json.dumps(skipped),
            "NEXT_PUBLIC_AEGIS_DATA_SOURCE": "fixture",
            "NEXT_PUBLIC_API_BASE_URL": "http://localhost:8000",
            "AEGIS_E2E_BASE_URL": "http://localhost:3000",
            "AEGIS_E2E_WORKERS": "1",
        }
    )
    if system_chromium is not None:
        environment["AEGIS_CHROMIUM_EXECUTABLE_PATH"] = str(system_chromium)
    command = [
        _pnpm_executable(),
        "--filter",
        "@aegis/web",
        "exec",
        "playwright",
        "test",
        "release/silent-relay.spec.ts",
        "--reporter=./../../tests/e2e/release/release-reporter.ts",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            env=environment,
            check=False,
            text=True,
        )
        exit_code = completed.returncode
    except OSError as exc:
        exit_code = 127
        print(f"E2E ERROR: unable to run Playwright: {exc}")

    if not output_path.exists():
        output_path.write_text(
            json.dumps(
                {
                    "schemaVersion": "aegis.release-e2e/v1",
                    "status": "failed",
                    "browsers": installed,
                    "skippedBrowsers": skipped,
                    "tests": [],
                    "error": "Playwright did not produce a release report",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        try:
            report_status = json.loads(output_path.read_text(encoding="utf-8")).get("status")
        except (OSError, json.JSONDecodeError):
            report_status = "failed"
        if report_status != "passed" and exit_code == 0:
            exit_code = 1
    print(f"E2E report: {output_path}")
    verdict = "PASS" if exit_code == 0 else "FAIL"
    print(f"RELEASE E2E: {verdict}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Start the deterministic Operation Silent Relay v1.0 local demo."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
from collections.abc import Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

DEFAULT_SEED = 42
SCENARIO_PACKAGE = "scenarios/operation-silent-relay"
SCENARIO_VERSION = "operation-silent-relay@1.0.0"
OPERATOR_ID = "user:operator-alpha"


def build_demo_manifest(*, seed: int = DEFAULT_SEED) -> dict[str, object]:
    """Return the checked-in contract for the demo's deterministic inputs/outcomes."""

    return {
        "schemaVersion": "aegis.demo/v1",
        "scenario": {
            "id": "scenario:operation-silent-relay",
            "version": SCENARIO_VERSION,
            "packageVersion": "1.0.0",
        },
        "seed": seed,
        "provider": "mock",
        "expectedHeadlineOutcomes": [
            "run starts with a persisted graph snapshot",
            "detection and model views remain advisory and evidence-linked",
            "agent investigation uses the mock provider",
            "state-changing proposals wait for explicit operator approval",
            "the run can be opened in replay and cinematic mode",
            "the after-action view exposes scoring and report review",
        ],
    }


class DemoError(RuntimeError):
    """Raised when the local demo cannot reach or use the local API."""


class DemoClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.cookies = http.cookiejar.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
        allow_not_found: bool = False,
    ) -> dict[str, object] | None:
        body = None
        request_headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        if headers:
            request_headers.update(headers)
        request = Request(
            f"{self.base_url}/{path.lstrip('/')}",
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=10) as response:
                value = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404 and allow_not_found:
                return None
            detail = exc.read().decode("utf-8", errors="replace")
            raise DemoError(f"{method} {path} returned HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise DemoError(f"{method} {path} could not reach the local API") from exc
        if not isinstance(value, dict):
            raise DemoError(f"{method} {path} returned a non-object JSON payload")
        return value

    def csrf_token(self) -> str:
        for cookie in self.cookies:
            if cookie.name == "aegis_csrf":
                return cookie.value
        raise DemoError("development login did not return an aegis_csrf cookie")


def run_demo(*, base_url: str, web_url: str, seed: int) -> str:
    client = DemoClient(base_url)
    client.request("GET", "/health")
    ready = client.request("GET", "/ready")
    if ready is None or ready.get("status") != "ready":
        raise DemoError("local API is not ready")
    client.request(
        "POST",
        "/api/v1/auth/dev/login",
        payload={"schemaVersion": 1, "userId": OPERATOR_ID},
    )
    csrf = client.csrf_token()
    deterministic_run_id = _deterministic_run_id(seed)
    existing = client.request(
        "GET",
        f"/api/v1/runs/{deterministic_run_id}",
        allow_not_found=True,
    )
    reused = existing is not None
    idempotency_key = f"demo-v1-silent-relay-seed-{seed}"
    if reused:
        run = existing
    else:
        created = client.request(
            "POST",
            "/api/v1/runs",
            payload={
                "schemaVersion": 1,
                "scenarioPackagePath": SCENARIO_PACKAGE,
                "seed": seed,
            },
            headers={"Idempotency-Key": idempotency_key, "X-CSRF-Token": csrf},
        )
        if created is None:
            raise DemoError("run creation returned no response")
        run = created.get("run")
    if not isinstance(run, dict) or not isinstance(run.get("id"), str):
        raise DemoError("run creation response did not include a run ID")
    run_id = run["id"]
    client.request("GET", f"/api/v1/runs/{run_id}/graph")

    reused_note = ", reused=true" if reused else ""
    print(f"DEMO: PASS (scenario={SCENARIO_VERSION}, seed={seed}, run={run_id}{reused_note})")
    print("Next steps:")
    print(f"  Live graph and timeline: {web_url.rstrip('/')}/runs/{run_id}")
    print(f"  Detection/ML observability: {base_url.rstrip('/')}/detection/observability")
    print(f"  Mock provider and agents: {base_url.rstrip('/')}/providers/observability")
    print(f"  Agent runtime workflow: {base_url.rstrip('/')}/agents/observability")
    print("  Approval: open the proposal surfaced by the incident investigation view")
    print(f"  Replay and cinematic mode: {web_url.rstrip('/')}/replay/{run_id}")
    print(f"  After-action review and scoring: {web_url.rstrip('/')}/after-action/{run_id}")
    print("  Grafana dashboards: http://localhost:3001")
    return run_id


def _deterministic_run_id(seed: int) -> str:
    """Match the simulation engine's stable run identity for this package/version."""

    from aegis_simulation_domain.ids import derive_run_id

    return derive_run_id(run_seed=seed, scenario_version_id="scenario-version:1.0.0")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("AEGIS_LOCAL_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--web-url", default=os.environ.get("AEGIS_LOCAL_WEB_URL", "http://localhost:3000"))
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--headless", action="store_true", help="run HTTP checks without opening a browser"
    )
    args = parser.parse_args(argv)
    _ = args.headless
    try:
        run_demo(base_url=args.base_url, web_url=args.web_url, seed=args.seed)
    except DemoError as exc:
        print(f"DEMO: FAIL - {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

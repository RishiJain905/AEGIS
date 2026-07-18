#!/usr/bin/env python3
"""Run deterministic local API, streaming, database, and browser measurements."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

REPORT_SCHEMA_VERSION = "aegis.release-performance/v1"
DETERMINISTIC_SEED = 42
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_WS_URL = "ws://127.0.0.1:8000/ws/v1/realtime"

# These are hard limits for the local production-like stack. The report keeps the
# measured value and budget together so a release decision is reproducible.
PERFORMANCE_BUDGETS: dict[str, dict[str, float]] = {
    "api.load.read": {"p50Ms": 300, "p95Ms": 500, "p99Ms": 750},
    "api.load.command": {"p50Ms": 300, "p95Ms": 750, "p99Ms": 1500},
    "stream.outbox_to_ws": {"p50Ms": 250, "p95Ms": 750, "p99Ms": 1500},
    "db.event_range_fetch": {"p50Ms": 100, "p95Ms": 300, "p99Ms": 750},
    "db.snapshot_load": {"p50Ms": 100, "p95Ms": 300, "p99Ms": 750},
    "db.incident_list": {"p50Ms": 100, "p95Ms": 300, "p99Ms": 750},
    "graph.2d.target_layout": {"p50Ms": 8000, "p95Ms": 8000, "p99Ms": 8000},
    "graph.2d.stress_layout": {"p50Ms": 20000, "p95Ms": 20000, "p99Ms": 20000},
    "graph.3d.mount_to_visible": {"p50Ms": 8000, "p95Ms": 8000, "p99Ms": 10000},
}


def percentile(values: Sequence[float], quantile: float) -> float:
    """Return an interpolated percentile using the nearest-rank position."""
    if not values:
        raise ValueError("percentile requires at least one sample")
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be between 0 and 1")
    ordered = sorted(float(value) for value in values)
    rank = (len(ordered) - 1) * quantile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 3)


def metric_report(
    name: str,
    values: Sequence[float],
    budget: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Build one report metric with p50/p95/p99 and an explicit budget result."""
    selected_budget = budget or PERFORMANCE_BUDGETS[name]
    report = {
        "metric": name,
        "sampleCount": len(values),
        "p50Ms": percentile(values, 0.50),
        "p95Ms": percentile(values, 0.95),
        "p99Ms": percentile(values, 0.99),
        "budgetMs": selected_budget,
    }
    report["status"] = (
        "passed"
        if all(report[key] <= selected_budget[key] for key in ("p50Ms", "p95Ms", "p99Ms"))
        else "failed"
    )
    return report


def _env_number(name: str, default: int | float) -> int | float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return type(default)(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric, got {raw!r}") from exc


def _iso_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


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
    return shutil.which("pnpm") or "pnpm"


def _configure_node_path() -> None:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return
    pnpm_bin = Path(os.environ.get("PNPM_HOME", Path(local_app_data) / "pnpm")) / "bin"
    if (pnpm_bin / "node.exe").exists():
        os.environ["PATH"] = f"{pnpm_bin}{os.pathsep}{os.environ.get('PATH', '')}"
    chromium_candidates = [
        os.environ.get("AEGIS_CHROMIUM_EXECUTABLE_PATH", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in chromium_candidates:
        if candidate and Path(candidate).exists():
            os.environ["AEGIS_CHROMIUM_EXECUTABLE_PATH"] = candidate
            break


async def _login(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/dev/login",
        json={"schemaVersion": 1, "userId": "user:operator-alpha"},
    )
    response.raise_for_status()
    payload = response.json()
    csrf = payload.get("session", {}).get("csrfToken")
    if not isinstance(csrf, str) or not csrf:
        raise RuntimeError("local API login did not return a CSRF token")
    client.headers["X-CSRF-Token"] = csrf


async def _request_timing(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    **kwargs: Any,
) -> tuple[float, httpx.Response]:
    started = time.perf_counter()
    response = await client.request(method, path, **kwargs)
    return (time.perf_counter() - started) * 1000, response


async def _select_run(client: httpx.AsyncClient) -> tuple[str, int]:
    response = await client.get("/api/v1/runs")
    response.raise_for_status()
    runs = response.json()
    if not isinstance(runs, list):
        raise RuntimeError("local API returned an invalid run list")

    for candidate in runs:
        run_id = candidate.get("id")
        if not isinstance(run_id, str):
            continue
        graph_response = await client.get(f"/api/v1/runs/{run_id}/graph")
        if graph_response.is_success:
            return run_id, int(candidate.get("seed", DETERMINISTIC_SEED))

    response, _ = await _request_timing(
        client,
        "POST",
        "/api/v1/runs",
        headers={"Idempotency-Key": "release-performance-create-42"},
        json={
            "schemaVersion": 1,
            "scenarioPackagePath": "scenarios/operation-silent-relay",
            "seed": DETERMINISTIC_SEED,
        },
    )
    response.raise_for_status()
    payload = response.json()
    run = payload.get("run")
    if not isinstance(run, dict) or not isinstance(run.get("id"), str):
        raise RuntimeError("local API did not return a run from the create command")
    return str(run["id"]), int(run.get("seed", DETERMINISTIC_SEED))


async def _api_load(
    client: httpx.AsyncClient,
    run_id: str,
    *,
    duration_seconds: float,
    concurrency: int,
    request_interval_seconds: float,
) -> tuple[list[float], list[float], list[str]]:
    read_paths = [
        "/api/v1/scenarios",
        "/api/v1/runs",
        f"/api/v1/runs/{run_id}/graph",
        f"/api/v1/runs/{run_id}/incidents",
        f"/api/v1/realtime/runs/{run_id}/events?limit=500",
    ]
    read_samples: list[float] = []
    command_samples: list[float] = []
    errors: list[str] = []
    deadline = time.perf_counter() + duration_seconds
    sample_lock = asyncio.Lock()

    async def read_worker(worker_id: int) -> None:
        index = worker_id
        while time.perf_counter() < deadline:
            path = read_paths[index % len(read_paths)]
            index += 1
            try:
                elapsed, response = await _request_timing(client, "GET", path)
                async with sample_lock:
                    if 200 <= response.status_code < 300:
                        read_samples.append(elapsed)
                    else:
                        errors.append(f"GET {path} returned HTTP {response.status_code}")
            except httpx.HTTPError as exc:
                async with sample_lock:
                    errors.append(f"GET {path} failed: {exc}")
            await asyncio.sleep(request_interval_seconds)

    async def command_worker() -> None:
        interval = max(1.0, duration_seconds / 5)
        while time.perf_counter() < deadline:
            try:
                elapsed, response = await _request_timing(
                    client,
                    "POST",
                    "/api/v1/realtime/backfill",
                    json={"schemaVersion": 1, "runId": run_id, "force": False},
                )
                async with sample_lock:
                    if 200 <= response.status_code < 300:
                        command_samples.append(elapsed)
                    else:
                        errors.append(
                            f"POST /api/v1/realtime/backfill returned HTTP {response.status_code}"
                        )
            except httpx.HTTPError as exc:
                async with sample_lock:
                    errors.append(f"POST /api/v1/realtime/backfill failed: {exc}")
            await asyncio.sleep(interval)

    await asyncio.gather(
        *(read_worker(worker_id) for worker_id in range(concurrency)),
        command_worker(),
    )
    return read_samples, command_samples, errors


async def _database_timings(run_id: str, *, sample_count: int) -> dict[str, list[float]]:
    from aegis_contracts import load_settings
    from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
    from aegis_persistence.mappers import incident_to_domain
    from aegis_persistence.orm.tables import IncidentRow
    from aegis_persistence.repositories.postgres import PostgresGraphSnapshotRepository
    from aegis_persistence.repositories.streaming import PostgresEventQueryRepository
    from sqlalchemy import select

    settings = load_settings()
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    values = {
        "db.event_range_fetch": [],
        "db.snapshot_load": [],
        "db.incident_list": [],
    }
    try:
        for _ in range(sample_count):
            async with session_maker() as session:
                started = time.perf_counter()
                await PostgresEventQueryRepository(session).list_by_run(
                    run_id,
                    from_sequence=0,
                    limit=5000,
                )
                values["db.event_range_fetch"].append((time.perf_counter() - started) * 1000)

                started = time.perf_counter()
                await PostgresGraphSnapshotRepository(session).get_latest_for_run(run_id)
                values["db.snapshot_load"].append((time.perf_counter() - started) * 1000)

                started = time.perf_counter()
                result = await session.execute(
                    select(IncidentRow)
                    .where(IncidentRow.run_id == run_id)
                    .order_by(IncidentRow.created_at)
                )
                for row in result.scalars().all():
                    incident_to_domain(row)
                values["db.incident_list"].append((time.perf_counter() - started) * 1000)
    finally:
        await dispose_engine(engine)
    return values


async def _append_stream_events(
    run_id: str,
    run_seed: int,
    *,
    count: int,
) -> list[tuple[str, datetime]]:
    from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1, load_settings
    from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION
    from aegis_event_streaming.redis_client import create_redis_client
    from aegis_event_streaming.relay import PostgresOutboxRelay
    from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
    from aegis_persistence.unit_of_work import PostgresUnitOfWork
    from aegis_simulation_domain.ids import derive_event_id, derive_trace_id

    settings = load_settings()
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    recorded: list[tuple[str, datetime]] = []
    try:
        async with PostgresUnitOfWork(session_maker, settings=settings) as uow:
            sequence = await uow.events.next_sequence(run_id)
            for index in range(count):
                event_sequence = sequence + index
                event_type = "telemetry.health.check"
                event_id = derive_event_id(
                    run_seed=run_seed + DETERMINISTIC_SEED,
                    sequence=event_sequence,
                    event_type=f"{event_type}:release:{index}",
                )
                trace_id = derive_trace_id(
                    run_seed=run_seed + DETERMINISTIC_SEED,
                    sequence=event_sequence,
                )
                now = datetime.now(UTC)
                event = DomainEventEnvelopeV1(
                    event_id=event_id,
                    run_id=run_id,
                    sequence=event_sequence,
                    type=event_type,
                    schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
                    sim_time=now,
                    recorded_at=now,
                    actor=ActorRef(type=ActorType.SYSTEM, id="asset:release-validation"),
                    subject=ActorRef(type=ActorType.ASSET, id="asset:svc-api-gateway"),
                    payload={"schemaVersion": 1, "releaseValidation": True, "burstIndex": index},
                    trace_id=trace_id,
                )
                await uow.append_event(event)
                recorded.append((event_id, now))

        redis = create_redis_client(settings)
        try:
            relay = PostgresOutboxRelay(session_maker, redis)
            for _ in range(10):
                published = await relay.publish_until_empty()
                if published >= count:
                    break
                await asyncio.sleep(0.05)
        finally:
            await redis.aclose()
    finally:
        await dispose_engine(engine)
    return recorded


async def _stream_lag(
    client: httpx.AsyncClient,
    run_id: str,
    run_seed: int,
    *,
    count: int,
    timeout_seconds: float,
) -> list[float]:
    try:
        from websockets.asyncio.client import connect
    except ImportError:
        try:
            from websockets import connect  # type: ignore[no-redef]
        except ImportError as exc:
            raise RuntimeError("websockets is required for event streaming lag validation") from exc

    ticket_response = await client.post("/api/v1/auth/ws-ticket")
    ticket_response.raise_for_status()
    ticket = ticket_response.json().get("ticket")
    if not isinstance(ticket, str) or not ticket:
        raise RuntimeError("local API did not return a WebSocket ticket")

    api_base = str(client.base_url).rstrip("/")
    ws_url = os.environ.get("AEGIS_RELEASE_WS_URL", api_base.replace("http", "ws", 1))
    ws_url = f"{ws_url}/ws/v1/realtime" if not ws_url.endswith("/ws/v1/realtime") else ws_url
    trace_id = "trc_01ARZ3NDEKTSV4RRFFQ69G5FCD"
    frame_base = {
        "schemaVersion": 1,
        "protocolVersion": 1,
        "traceId": trace_id,
        "sentAt": _iso_now(),
    }

    async with connect(ws_url, open_timeout=10, close_timeout=2) as websocket:
        await websocket.send(
            json.dumps(
                {
                    **frame_base,
                    "messageType": "hello",
                    "payload": {"protocolVersion": 1, "authToken": ticket},
                }
            )
        )
        hello_ack = json.loads(await asyncio.wait_for(websocket.recv(), timeout=10))
        if hello_ack.get("messageType") != "hello_ack":
            raise RuntimeError(f"unexpected WebSocket hello response: {hello_ack}")

        events_response = await client.get(f"/api/v1/realtime/runs/{run_id}/events?limit=1")
        events_response.raise_for_status()
        existing_events = events_response.json().get("events", [])
        last_sequence = max((int(event.get("sequence", 0)) for event in existing_events), default=0)
        await websocket.send(
            json.dumps(
                {
                    **frame_base,
                    "messageType": "subscribe",
                    "payload": {
                        "runId": run_id,
                        "channel": "events",
                        "lastAppliedSequence": last_sequence,
                    },
                }
            )
        )
        subscribed = json.loads(await asyncio.wait_for(websocket.recv(), timeout=10))
        if subscribed.get("messageType") != "subscribed":
            raise RuntimeError(f"unexpected WebSocket subscribe response: {subscribed}")

        recorded = await _append_stream_events(run_id, run_seed, count=count)
        expected = {event_id: recorded_at for event_id, recorded_at in recorded}
        latencies: list[float] = []
        deadline = time.perf_counter() + timeout_seconds
        while expected and time.perf_counter() < deadline:
            try:
                raw = await asyncio.wait_for(websocket.recv(), timeout=1)
            except TimeoutError:
                continue
            frame = json.loads(raw)
            if frame.get("messageType") != "event":
                continue
            event = frame.get("payload", {}).get("envelope", {}).get("event", {})
            event_id = event.get("eventId")
            recorded_at = expected.pop(event_id, None)
            if recorded_at is None:
                continue
            latencies.append(max(0.0, (datetime.now(UTC) - recorded_at).total_seconds() * 1000))
        if expected:
            raise RuntimeError(f"WebSocket did not deliver {len(expected)} burst events")
        return latencies


def _browser_measurement(report_path: Path) -> dict[str, Any]:
    browser_report_path = report_path.with_name("browser-performance.json")
    environment = os.environ.copy()
    environment.update(
        {
            "AEGIS_RELEASE_BROWSER_PERFORMANCE_REPORT_PATH": str(browser_report_path),
            "AEGIS_BROWSER_PROJECTS": "chromium",
            "NEXT_PUBLIC_AEGIS_DATA_SOURCE": "fixture",
            "NEXT_PUBLIC_API_BASE_URL": "http://localhost:8000",
            "AEGIS_E2E_BASE_URL": "http://localhost:3100",
            "AEGIS_E2E_LOCAL_WEB": "1",
            "AEGIS_E2E_WEB_PORT": "3100",
            "AEGIS_E2E_WORKERS": "1",
        }
    )
    command = [
        _pnpm_executable(),
        "--filter",
        "@aegis/web",
        "exec",
        "playwright",
        "test",
        "release/browser-performance.spec.ts",
        "--project=chromium",
        "--reporter=line",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[3],
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return {"status": "failed", "error": f"unable to run Playwright: {exc}"}
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    browser_payload: dict[str, Any] = {}
    if browser_report_path.exists():
        browser_payload = json.loads(browser_report_path.read_text(encoding="utf-8"))
    browser_payload["exitCode"] = completed.returncode
    if completed.returncode != 0:
        browser_payload["status"] = "failed"
        browser_payload.setdefault("error", "Playwright browser performance measurement failed")
    return browser_payload


async def collect_report(report_path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    report: dict[str, Any] = {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "startedAt": _iso_now(),
        "environment": "local",
        "scenario": {"version": "operation-silent-relay@1.0.0", "seed": DETERMINISTIC_SEED},
        "budgets": PERFORMANCE_BUDGETS,
        "metrics": [],
        "skips": [],
        "errors": [],
        "status": "failed",
    }
    try:
        api_base = os.environ.get("AEGIS_RELEASE_API_URL", DEFAULT_API_BASE_URL)
        duration_seconds = float(_env_number("AEGIS_PERF_DURATION_SECONDS", 30.0))
        concurrency = int(_env_number("AEGIS_PERF_CONCURRENCY", 20))
        interval = float(_env_number("AEGIS_PERF_REQUEST_INTERVAL_SECONDS", 10.0))
        db_samples = int(_env_number("AEGIS_PERF_DB_SAMPLES", 20))
        stream_count = int(_env_number("AEGIS_PERF_STREAM_EVENTS", 20))
        stream_timeout = float(_env_number("AEGIS_PERF_STREAM_TIMEOUT_SECONDS", 15.0))
        if duration_seconds <= 0 or concurrency <= 0 or db_samples <= 0 or stream_count <= 0:
            raise ValueError("performance sample counts and duration must be positive")

        async with httpx.AsyncClient(base_url=api_base, timeout=15.0) as client:
            await _login(client)
            run_id, run_seed = await _select_run(client)
            report["runId"] = run_id
            read_samples, command_samples, errors = await _api_load(
                client,
                run_id,
                duration_seconds=duration_seconds,
                concurrency=concurrency,
                request_interval_seconds=interval,
            )
            report["errors"].extend(errors)
            if not read_samples or not command_samples:
                raise RuntimeError("API load did not produce read and command samples")
            report["metrics"].append(metric_report("api.load.read", read_samples))
            report["metrics"].append(metric_report("api.load.command", command_samples))

            db_values = await _database_timings(run_id, sample_count=db_samples)
            for name, values in db_values.items():
                report["metrics"].append(metric_report(name, values))

            stream_values = await _stream_lag(
                client,
                run_id,
                run_seed,
                count=stream_count,
                timeout_seconds=stream_timeout,
            )
            report["metrics"].append(metric_report("stream.outbox_to_ws", stream_values))

        browser_payload = _browser_measurement(report_path)
        report["browser"] = browser_payload
        report["metrics"].extend(browser_payload.get("metrics", []))
        report["skips"].extend(browser_payload.get("skips", []))
        if browser_payload.get("status") != "passed":
            report["errors"].append(browser_payload.get("error", "browser measurement failed"))

        report["status"] = (
            "passed"
            if not report["errors"]
            and all(metric.get("status") in {"passed", "skipped"} for metric in report["metrics"])
            and browser_payload.get("status") == "passed"
            else "failed"
        )
    except Exception as exc:  # noqa: BLE001 - the report must survive stage failures.
        report["errors"].append(str(exc))
        report["status"] = "failed"
    report["durationSeconds"] = round(time.perf_counter() - started, 3)
    await asyncio.to_thread(_write_report, report_path, report)
    return report


def _write_report(report_path: Path, report: dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    _configure_node_path()
    report_path = Path(
        os.environ.get(
            "AEGIS_RELEASE_REPORT_PATH",
            "docs/release/evidence/performance-report.json",
        )
    ).resolve()
    report = asyncio.run(collect_report(report_path))
    print(f"Performance report: {report_path}")
    verdict = "PASS" if report["status"] == "passed" else "FAIL"
    print(f"PERFORMANCE BUDGET: {verdict}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

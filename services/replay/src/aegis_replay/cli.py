"""CLI diagnostic harness for Phase 25 snapshot and replay engine."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis_contracts import SnapshotTriggerReasonV1, load_settings
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.object_storage import ObjectStorageError, build_object_storage
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from aegis_replay.errors import ReplayEngineError
from aegis_replay.service import ReplayService


def _dump(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json", by_alias=True)
    if isinstance(model, dict):
        return model
    return {"value": str(model)}


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _build_service() -> ReplayService:
    settings = load_settings()
    filesystem_root = os.environ.get("AEGIS_REPLAY_STORAGE_DIR")
    in_memory = os.environ.get("AEGIS_REPLAY_IN_MEMORY_STORAGE", "").lower() in {
        "1",
        "true",
        "yes",
    }
    storage = build_object_storage(
        settings,
        in_memory=in_memory and not filesystem_root,
        filesystem_root=filesystem_root,
    )
    return ReplayService(storage)


async def _with_uow(coro_factory):  # type: ignore[no-untyped-def]
    settings = load_settings()
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    try:
        async with PostgresUnitOfWork(session_maker) as uow:
            return await coro_factory(uow)
    finally:
        await dispose_engine(engine)


async def cmd_create_snapshot(args: argparse.Namespace) -> int:
    service = _build_service()

    async def _run(uow: PostgresUnitOfWork) -> dict[str, Any]:
        manifest = await service.create_snapshot(
            uow,
            run_id=args.run_id,
            sequence=args.sequence,
            trigger_reason=SnapshotTriggerReasonV1(args.trigger_reason),
        )
        return _dump(manifest)

    try:
        payload = await _with_uow(_run)
    except ReplayEngineError as exc:
        _print_json(exc.to_dict())
        return 2
    _print_json(payload)
    return 0


async def cmd_reconstruct(args: argparse.Namespace) -> int:
    service = _build_service()

    async def _run(uow: PostgresUnitOfWork) -> dict[str, Any]:
        state = await service.reconstruct(
            uow,
            run_id=args.run_id,
            sequence=args.sequence,
            prefer_snapshot=not args.from_events_only,
            incident_id=args.incident_id,
        )
        return _dump(state)

    try:
        payload = await _with_uow(_run)
    except ReplayEngineError as exc:
        _print_json(exc.to_dict())
        return 2
    _print_json(payload)
    return 0


async def cmd_equivalence(args: argparse.Namespace) -> int:
    service = _build_service()

    async def _run(uow: PostgresUnitOfWork) -> dict[str, Any]:
        result = await service.check_equivalence(
            uow,
            run_id=args.run_id,
            sequence=args.sequence,
        )
        return _dump(result)

    try:
        payload = await _with_uow(_run)
    except ReplayEngineError as exc:
        _print_json(exc.to_dict())
        return 2
    _print_json(payload)
    return 0 if payload.get("equivalent") else 3


async def cmd_list_snapshots(args: argparse.Namespace) -> int:
    service = _build_service()

    async def _run(uow: PostgresUnitOfWork) -> list[dict[str, Any]]:
        manifests = await service.list_snapshots(uow, run_id=args.run_id)
        return [_dump(item) for item in manifests]

    payload = await _with_uow(_run)
    _print_json(payload)
    return 0


async def cmd_corrupt_reject_demo(args: argparse.Namespace) -> int:
    """Demonstrate safe rejection of a tampered snapshot archive."""
    service = _build_service()
    storage = service._store._storage

    async def _run(uow: PostgresUnitOfWork) -> dict[str, Any]:
        manifests = [
            item
            for item in await service.list_snapshots(uow, run_id=args.run_id)
            if item.compatible and storage.exists(object_key=item.object_key)
        ]
        if not manifests:
            manifest = await service.create_snapshot(uow, run_id=args.run_id)
        else:
            manifest = manifests[-1]
        original = storage.get_bytes(object_key=manifest.object_key)
        tampered = original[:-8] + b"DEADBEEF"
        storage.put_bytes(
            object_key=manifest.object_key,
            data=tampered,
            content_type=manifest.content_type,
        )
        try:
            await service._store.load_snapshot(uow, manifest.snapshot_id)
            outcome = {"rejected": False}
        except ReplayEngineError as exc:
            outcome = {"rejected": True, "error": exc.to_dict()}
        # Restore original bytes so later demos can continue; leave manifest
        # marked incompatible after checksum failure (fail-closed semantics).
        with contextlib.suppress(ObjectStorageError):
            storage.put_bytes(
                object_key=manifest.object_key,
                data=original,
                content_type=manifest.content_type,
            )
        return {
            "snapshotId": manifest.snapshot_id,
            "objectKey": manifest.object_key,
            "demo": "corrupt_checksum_reject",
            **outcome,
        }

    payload = await _with_uow(_run)
    _print_json(payload)
    return 0 if payload.get("rejected") else 4


async def cmd_gap_detect_demo(args: argparse.Namespace) -> int:
    """Demonstrate sequence-gap detection using an injected synthetic gap."""
    from aegis_contracts import DomainEventEnvelopeV1

    # Pure in-memory demonstration — does not mutate PostgreSQL.
    base_time = datetime(2026, 1, 1, 18, 0, 0, tzinfo=UTC)

    def _event(sequence: int, event_id_suffix: str) -> DomainEventEnvelopeV1:
        return DomainEventEnvelopeV1.model_validate(
            {
                "eventId": f"evt_01ARZ3NDEKTSV4RRFFQ69G5F{event_id_suffix}",
                "runId": args.run_id,
                "sequence": sequence,
                "type": "sim.run.started",
                "schemaVersion": 1,
                "simTime": base_time.isoformat().replace("+00:00", "Z"),
                "recordedAt": base_time.isoformat().replace("+00:00", "Z"),
                "actor": {"type": "system", "id": "asset:simulation-engine"},
                "subject": {"type": "system", "id": "asset:simulation-engine"},
                "payload": {
                    "scenarioVersionId": "scenario-version:v1.0.0-synthetic",
                    "seed": 42,
                },
                "traceId": "trc_01ARZ3NDEKTSV4RRFFQ69G5FAX",
            }
        )

    events = [_event(1, "A1"), _event(3, "A3")]  # gap at sequence 2
    detected: dict[str, Any] | None = None
    try:
        service = _build_service()
        service._assert_sequence_contiguous(events, up_to=3)
    except ReplayEngineError as exc:
        detected = exc.to_dict()
    _print_json(
        {
            "demo": "sequence_gap_detect",
            "detected": detected is not None,
            "error": detected,
            "note": "Live PostgreSQL history was not mutated",
        }
    )
    return 0 if detected is not None else 5


async def cmd_diagnostic_page(args: argparse.Namespace) -> int:
    """Write a static HTML diagnostic page for screenshot capture."""
    service = _build_service()

    async def _run(uow: PostgresUnitOfWork) -> dict[str, Any]:
        state = await service.reconstruct(uow, run_id=args.run_id, sequence=args.sequence)
        snapshots = await service.list_snapshots(uow, run_id=args.run_id)
        equivalence = await service.check_equivalence(
            uow,
            run_id=args.run_id,
            sequence=args.sequence,
        )
        return {
            "generatedAt": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
            "mode": "historical_replay",
            "liveMutationAllowed": False,
            "runId": args.run_id,
            "state": _dump(state),
            "snapshots": [_dump(item) for item in snapshots],
            "equivalence": _dump(equivalence),
        }

    try:
        payload = await _with_uow(_run)
    except ReplayEngineError as exc:
        _print_json(exc.to_dict())
        return 2

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AEGIS Phase 25 Replay Diagnostic</title>
  <style>
    :root {{
      --bg: #0f1419;
      --panel: #1a2332;
      --text: #e7ecf3;
      --muted: #9aa7b8;
      --accent: #3d9cf0;
      --ok: #3ecf8e;
      --bad: #f07178;
      --line: #2a3648;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      background: radial-gradient(1200px 600px at 10% -10%, #1b2a44, var(--bg));
      color: var(--text); padding: 24px;
    }}
    h1 {{ font-family: "IBM Plex Mono", monospace; font-weight: 600; letter-spacing: 0.02em; }}
    .banner {{
      border: 1px solid var(--line); background: var(--panel); padding: 16px 20px;
      margin-bottom: 20px; display: flex; gap: 24px; flex-wrap: wrap; align-items: center;
    }}
    .badge {{
      display: inline-block; padding: 4px 10px; border: 1px solid var(--accent);
      color: var(--accent); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em;
    }}
    .grid {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px;
    }}
    section {{
      background: var(--panel); border: 1px solid var(--line); padding: 16px;
      min-height: 180px;
    }}
    h2 {{ margin: 0 0 12px; font-size: 14px; color: var(--muted); text-transform: uppercase; }}
    pre {{
      margin: 0; white-space: pre-wrap; word-break: break-word; font-size: 12px;
      font-family: "IBM Plex Mono", monospace; line-height: 1.45;
      max-height: 360px; overflow: auto;
    }}
    .ok {{ color: var(--ok); }}
    .bad {{ color: var(--bad); }}
    .meta {{ color: var(--muted); font-size: 13px; }}
  </style>
</head>
<body>
  <h1>AEGIS Phase 25 — Snapshot & Replay Engine</h1>
  <div class="banner">
    <span class="badge" id="mode-badge">HISTORICAL REPLAY</span>
    <div class="meta">Run: <strong id="run-id"></strong></div>
    <div class="meta">Live mutation allowed: <strong id="live-flag" class="ok">false</strong></div>
    <div class="meta">Equivalence: <strong id="equiv-flag"></strong></div>
    <div class="meta">Generated: <span id="generated-at"></span></div>
  </div>
  <div class="grid">
    <section>
      <h2>Snapshot manifests</h2>
      <pre id="snapshots"></pre>
    </section>
    <section>
      <h2>Provenance</h2>
      <pre id="provenance"></pre>
    </section>
    <section>
      <h2>Reconstructed state digest</h2>
      <pre id="digest"></pre>
    </section>
    <section>
      <h2>Graph / incidents / approvals</h2>
      <pre id="domains"></pre>
    </section>
    <section>
      <h2>Equivalence result</h2>
      <pre id="equivalence"></pre>
    </section>
    <section>
      <h2>Full diagnostic JSON</h2>
      <pre id="full"></pre>
    </section>
  </div>
  <script>
    const data = {json.dumps(payload)};
    document.getElementById('run-id').textContent = data.runId;
    document.getElementById('generated-at').textContent = data.generatedAt;
    document.getElementById('live-flag').textContent = String(data.liveMutationAllowed);
    const eq = data.equivalence && data.equivalence.equivalent;
    const equivEl = document.getElementById('equiv-flag');
    equivEl.textContent = eq ? 'PASS' : 'FAIL';
    equivEl.className = eq ? 'ok' : 'bad';
    document.getElementById('snapshots').textContent = JSON.stringify(data.snapshots, null, 2);
    document.getElementById('provenance').textContent =
      JSON.stringify(data.state.provenance, null, 2);
    document.getElementById('digest').textContent = data.state.stateDigest;
    document.getElementById('domains').textContent = JSON.stringify({{
      graphNodes: (data.state.graph && data.state.graph.nodes) ? data.state.graph.nodes.length : 0,
      incidents: data.state.incidents,
      proposals: data.state.proposals,
      approvals: data.state.approvals,
      executedActions: data.state.executedActions,
      reports: data.state.reports,
      auditEvents: data.state.auditEvents.slice(0, 20),
    }}, null, 2);
    document.getElementById('equivalence').textContent = JSON.stringify(data.equivalence, null, 2);
    document.getElementById('full').textContent = JSON.stringify(data, null, 2);
  </script>
</body>
</html>
"""
    output_path = Path(args.output)
    await asyncio.to_thread(output_path.write_text, html, "utf-8")
    print(f"Wrote diagnostic page: {args.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aegis-replay")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-snapshot", help="Create a replay snapshot at a sequence")
    create.add_argument("--run-id", required=True)
    create.add_argument("--sequence", type=int, default=None)
    create.add_argument(
        "--trigger-reason",
        default=SnapshotTriggerReasonV1.EXPLICIT_REQUEST.value,
        choices=[item.value for item in SnapshotTriggerReasonV1],
    )
    create.set_defaults(func=cmd_create_snapshot)

    reconstruct = sub.add_parser("reconstruct", help="Reconstruct replay state")
    reconstruct.add_argument("--run-id", required=True)
    reconstruct.add_argument("--sequence", type=int, default=None)
    reconstruct.add_argument("--incident-id", default=None)
    reconstruct.add_argument(
        "--from-events-only",
        action="store_true",
        help="Ignore snapshots and rebuild from sequence 0",
    )
    reconstruct.set_defaults(func=cmd_reconstruct)

    equivalence = sub.add_parser("equivalence", help="Compare event-only vs snapshot replay")
    equivalence.add_argument("--run-id", required=True)
    equivalence.add_argument("--sequence", type=int, default=None)
    equivalence.set_defaults(func=cmd_equivalence)

    listing = sub.add_parser("list-snapshots", help="List snapshot manifests for a run")
    listing.add_argument("--run-id", required=True)
    listing.set_defaults(func=cmd_list_snapshots)

    corrupt = sub.add_parser(
        "corrupt-reject-demo",
        help="Tamper a snapshot archive and show safe rejection",
    )
    corrupt.add_argument("--run-id", required=True)
    corrupt.set_defaults(func=cmd_corrupt_reject_demo)

    gap = sub.add_parser("gap-detect-demo", help="Demonstrate sequence gap detection")
    gap.add_argument("--run-id", default="run_01ARZ3NDEKTSV4RRFFQ69G5FAV")
    gap.set_defaults(func=cmd_gap_detect_demo)

    page = sub.add_parser("diagnostic-page", help="Write HTML diagnostic harness page")
    page.add_argument("--run-id", required=True)
    page.add_argument("--sequence", type=int, default=None)
    page.add_argument(
        "--output",
        default="/opt/cursor/artifacts/replay-diagnostic.html",
    )
    page.set_defaults(func=cmd_diagnostic_page)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    exit_code = asyncio.run(args.func(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

"""aegis-simulator CLI for deterministic simulation operations."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from aegis_contracts import ActorRef, ActorType, SimulationCommandType, load_settings
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_simulation_domain import SimulationEngine, SimulationError
from aegis_simulation_domain.runtime import SIMULATION_ENGINE_VERSION

from aegis_simulation.application import SimulationApplicationService


def _print_json(data: object) -> None:
    print(json.dumps(data, indent=2, sort_keys=True, default=str))


def _run_local(
    package_dir: Path,
    *,
    seed: int,
    steps: int,
) -> dict[str, object]:
    manifest = SimulationEngine.load_manifest(package_dir)
    scenario_version_id = f"scenario-version:{manifest.metadata.version}"
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=seed,
        scenario_version_id=scenario_version_id,
    )
    runtime.start()
    runtime.run_steps(steps)
    normalized = SimulationEngine.normalized_hash(runtime, scenario_version_id=scenario_version_id)
    return {
        "runId": runtime.run_id,
        "engineVersion": SIMULATION_ENGINE_VERSION,
        "eventCount": normalized.event_count,
        "normalizedHash": normalized.hash_value,
        "finalSimTime": runtime.clock.sim_time.isoformat().replace("+00:00", "Z"),
        "status": runtime.world.status.value,
    }


def _determinism_check(package_dir: Path, *, seed: int, steps: int) -> dict[str, object]:
    first = _run_local(package_dir, seed=seed, steps=steps)
    second = _run_local(package_dir, seed=seed, steps=steps)
    return {
        "seed": seed,
        "steps": steps,
        "firstHash": first["normalizedHash"],
        "secondHash": second["normalizedHash"],
        "deterministic": first["normalizedHash"] == second["normalizedHash"],
        "engineVersion": SIMULATION_ENGINE_VERSION,
    }


def _checkpoint_recovery_check(
    package_dir: Path, *, seed: int, steps: int, checkpoint_at: int
) -> dict[str, object]:
    from aegis_simulation_domain.normalized_hash import compute_normalized_event_hash

    manifest = SimulationEngine.load_manifest(package_dir)
    scenario_version_id = f"scenario-version:{manifest.metadata.version}"

    uninterrupted = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=seed,
        scenario_version_id=scenario_version_id,
    )
    uninterrupted.start()
    uninterrupted.run_steps(checkpoint_at)
    uninterrupted.checkpoint()
    uninterrupted.run_steps(steps - checkpoint_at)
    uninterrupted_hash = SimulationEngine.normalized_hash(
        uninterrupted,
        scenario_version_id=scenario_version_id,
    ).hash_value

    checkpoint_runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=seed,
        scenario_version_id=scenario_version_id,
    )
    checkpoint_runtime.start()
    checkpoint_runtime.run_steps(checkpoint_at)
    checkpoint = checkpoint_runtime.checkpoint()
    events_before = list(checkpoint_runtime.events)

    restored = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=seed,
        scenario_version_id=scenario_version_id,
    )
    restored.restore(checkpoint)
    restored.run_steps(steps - checkpoint_at)
    restored_hash = compute_normalized_event_hash(
        events=events_before + restored.events,
        scenario_version_id=scenario_version_id,
        seed=seed,
        engine_version=SIMULATION_ENGINE_VERSION,
    ).hash_value

    return {
        "seed": seed,
        "steps": steps,
        "checkpointAt": checkpoint_at,
        "checkpointId": checkpoint.id,
        "uninterruptedHash": uninterrupted_hash,
        "restoredHash": restored_hash,
        "recoveryMatches": uninterrupted_hash == restored_hash,
        "engineVersion": SIMULATION_ENGINE_VERSION,
    }


def _seed_divergence_check(
    package_dir: Path, *, seed_a: int, seed_b: int, steps: int
) -> dict[str, object]:
    run_a = _run_local(package_dir, seed=seed_a, steps=steps)
    run_b = _run_local(package_dir, seed=seed_b, steps=steps)
    return {
        "seedA": seed_a,
        "seedB": seed_b,
        "hashA": run_a["normalizedHash"],
        "hashB": run_b["normalizedHash"],
        "different": run_a["normalizedHash"] != run_b["normalizedHash"],
        "bothValid": bool(run_a["normalizedHash"]) and bool(run_b["normalizedHash"]),
    }


def _invalid_command_demo() -> dict[str, object]:
    from aegis_contracts import SimulationCommandV1
    from aegis_contracts.versioning import SIMULATION_COMMAND_SCHEMA_VERSION

    package_dir = Path("scenarios/_fixtures/valid-minimal")
    manifest = SimulationEngine.load_manifest(package_dir)
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=42,
        scenario_version_id="scenario-version:1.0.0-fixture",
    )
    runtime.start()
    command = SimulationCommandV1(
        schema_version=SIMULATION_COMMAND_SCHEMA_VERSION,
        command_id="cmd-invalid-agent",
        command_type=SimulationCommandType.EXECUTE,
        run_id=runtime.run_id,
        actor=ActorRef(type=ActorType.AGENT, id="agent-session:test"),
        authorization_token=None,
        payload={"pluginId": "effect.set_asset_status", "config": {"status": "compromised"}},
    )
    try:
        runtime.execute_command(command)
        return {"rejected": False, "error": None}
    except SimulationError as exc:
        return {"rejected": True, "errorCode": exc.code.value, "message": exc.message}


async def _run_persisted(
    package_dir: Path,
    *,
    seed: int,
    steps: int,
    run_id: str | None = None,
) -> dict[str, object]:
    settings = load_settings()
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    try:
        async with PostgresUnitOfWork(session_maker) as uow:
            service = SimulationApplicationService(uow)
            runtime, manifest = await service.create_run_from_package(
                package_dir,
                seed=seed,
                run_id=run_id,
            )
            await service.execute_command(
                runtime,
                service.build_command(
                    command_id=f"cmd-start-{seed}",
                    command_type=SimulationCommandType.START,
                    run_id=runtime.run_id,
                ),
            )
            for index in range(steps):
                await service.execute_command(
                    runtime,
                    service.build_command(
                        command_id=f"cmd-step-{seed}-{index}",
                        command_type=SimulationCommandType.STEP,
                        run_id=runtime.run_id,
                    ),
                )
            scenario_version_id = f"scenario-version:{manifest.metadata.version}"
            normalized = SimulationEngine.normalized_hash(
                runtime,
                scenario_version_id=scenario_version_id,
            )
            await uow.commit()
            return {
                "runId": runtime.run_id,
                "engineVersion": SIMULATION_ENGINE_VERSION,
                "eventCount": normalized.event_count,
                "normalizedHash": normalized.hash_value,
                "finalSimTime": runtime.clock.sim_time.isoformat().replace("+00:00", "Z"),
                "status": runtime.world.status.value,
                "persisted": True,
            }
    finally:
        await dispose_engine(engine)


def main() -> None:
    parser = argparse.ArgumentParser(prog="aegis-simulator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a local in-memory simulation")
    run_parser.add_argument("--scenario", type=Path, required=True)
    run_parser.add_argument("--seed", type=int, default=42)
    run_parser.add_argument("--steps", type=int, default=50)

    persisted_parser = subparsers.add_parser(
        "run-persisted",
        help="Run simulation with PostgreSQL event persistence",
    )
    persisted_parser.add_argument("--scenario", type=Path, required=True)
    persisted_parser.add_argument("--seed", type=int, default=42)
    persisted_parser.add_argument("--steps", type=int, default=50)
    persisted_parser.add_argument("--run-id", type=str, default=None)

    determinism_parser = subparsers.add_parser("determinism-check")
    determinism_parser.add_argument("--scenario", type=Path, required=True)
    determinism_parser.add_argument("--seed", type=int, default=42)
    determinism_parser.add_argument("--steps", type=int, default=50)

    recovery_parser = subparsers.add_parser("checkpoint-recovery-check")
    recovery_parser.add_argument("--scenario", type=Path, required=True)
    recovery_parser.add_argument("--seed", type=int, default=42)
    recovery_parser.add_argument("--steps", type=int, default=50)
    recovery_parser.add_argument("--checkpoint-at", type=int, default=10)

    divergence_parser = subparsers.add_parser("seed-divergence-check")
    divergence_parser.add_argument("--scenario", type=Path, required=True)
    divergence_parser.add_argument("--seed-a", type=int, default=42)
    divergence_parser.add_argument("--seed-b", type=int, default=99)
    divergence_parser.add_argument("--steps", type=int, default=50)

    subparsers.add_parser("invalid-command-demo")

    health_parser = subparsers.add_parser("health")
    health_parser.add_argument("--service", default="simulator")

    args = parser.parse_args()

    try:
        if args.command == "health":
            from aegis_simulation import get_health

            health = get_health(args.service)
            print(f"{health.service} {health.status} {health.version}")
            return
        if args.command == "run":
            _print_json(_run_local(args.scenario, seed=args.seed, steps=args.steps))
            return
        if args.command == "run-persisted":
            _print_json(
                asyncio.run(
                    _run_persisted(
                        args.scenario,
                        seed=args.seed,
                        steps=args.steps,
                        run_id=args.run_id,
                    )
                )
            )
            return
        if args.command == "determinism-check":
            result = _determinism_check(args.scenario, seed=args.seed, steps=args.steps)
            _print_json(result)
            if not result["deterministic"]:
                sys.exit(1)
            return
        if args.command == "checkpoint-recovery-check":
            result = _checkpoint_recovery_check(
                args.scenario,
                seed=args.seed,
                steps=args.steps,
                checkpoint_at=args.checkpoint_at,
            )
            _print_json(result)
            if not result["recoveryMatches"]:
                sys.exit(1)
            return
        if args.command == "seed-divergence-check":
            _print_json(
                _seed_divergence_check(
                    args.scenario,
                    seed_a=args.seed_a,
                    seed_b=args.seed_b,
                    steps=args.steps,
                )
            )
            return
        if args.command == "invalid-command-demo":
            _print_json(_invalid_command_demo())
            return
    except SimulationError as exc:
        print(json.dumps({"error": exc.code.value, "message": exc.message, "details": exc.details}))
        sys.exit(1)


if __name__ == "__main__":
    main()

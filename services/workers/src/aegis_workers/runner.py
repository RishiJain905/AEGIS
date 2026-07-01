"""Minimal worker process entrypoint with outbox relay mode."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time

from aegis_workers import get_health


def main() -> None:
    parser = argparse.ArgumentParser(prog="aegis-worker")
    parser.add_argument(
        "--mode",
        choices=["health", "outbox-relay"],
        default=os.environ.get("AEGIS_WORKER_MODE", "health"),
    )
    args = parser.parse_args()

    if args.mode == "outbox-relay":
        from aegis_workers.outbox.relay_runner import main as relay_main

        relay_main()
        return

    health = get_health("worker")
    print(f"{health.service} {health.status} {health.version}", flush=True)

    def handle_signal(_signum: int, _frame: object) -> None:
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()

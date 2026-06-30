"""Minimal worker process entrypoint for Phase 00 infrastructure."""

import signal
import sys
import time

from aegis_workers import get_health


def main() -> None:
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

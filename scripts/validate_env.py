#!/usr/bin/env python3
"""Validate local environment variables using shared Python settings."""

from __future__ import annotations

import sys

from aegis_contracts import load_settings


def main() -> int:
    settings = load_settings()
    print(
        f"Environment valid: {settings.AEGIS_ENV.value} "
        f"(API {settings.API_PORT}, WEB {settings.WEB_PORT})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

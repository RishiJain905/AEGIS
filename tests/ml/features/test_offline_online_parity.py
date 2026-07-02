"""Offline/online parity tests."""

from __future__ import annotations

from aegis_ml.features.parity import run_offline_online_parity

from tests.ml.features.helpers import RUN_ID, sample_auth_failed, sample_auth_succeeded


def test_offline_and_online_paths_match() -> None:
    events = [sample_auth_failed(), sample_auth_succeeded()]
    parity = run_offline_online_parity(run_id=RUN_ID, events=events)
    assert parity.matching is True
    assert parity.offline_checksum == parity.online_checksum
    assert parity.vector_count == 1

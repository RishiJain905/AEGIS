"""Shared offline/online feature computation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from aegis_contracts.events import DomainEventEnvelopeV1
from aegis_contracts.features import (
    TRANSFORM_VERSION,
    FeatureComputeResponseV1,
    FeatureErrorCode,
    FeatureProvenanceV1,
    FeatureRejectionV1,
    FeatureSchemaManifestV1,
    FeatureVectorV1,
    FeatureWindowV1,
)
from aegis_contracts.versioning import (
    FEATURE_COMPUTE_RESPONSE_SCHEMA_VERSION,
    FEATURE_SCHEMA_VERSION,
    FEATURE_VECTOR_SCHEMA_VERSION,
    FEATURE_WINDOW_SCHEMA_VERSION,
)

from aegis_ml.features.aggregators import WindowAccumulator, accumulator_to_values
from aegis_ml.features.input_guard import classify_event, extract_asset_id
from aegis_ml.features.ordering import sort_events_by_sequence
from aegis_ml.features.schema_registry import FEATURE_SCHEMA_MANIFEST_V1
from aegis_ml.features.windows import (
    build_window_key,
    window_bounds,
    window_start_epoch,
)


@dataclass
class FeatureTransformResult:
    vectors: list[FeatureVectorV1] = field(default_factory=list)
    windows: list[FeatureWindowV1] = field(default_factory=list)
    rejections: list[FeatureRejectionV1] = field(default_factory=list)
    last_processed_sequence: int = 0


@dataclass
class FeatureTransformEngine:
    manifest: FeatureSchemaManifestV1 = field(default_factory=lambda: FEATURE_SCHEMA_MANIFEST_V1)
    run_id: str = ""
    seen_event_ids: set[str] = field(default_factory=set)
    closed_windows: set[str] = field(default_factory=set)
    open_accumulators: dict[str, WindowAccumulator] = field(default_factory=dict)
    entity_latest_window_start: dict[str, int] = field(default_factory=dict)

    def reset(self, *, run_id: str) -> None:
        self.run_id = run_id
        self.seen_event_ids.clear()
        self.closed_windows.clear()
        self.open_accumulators.clear()
        self.entity_latest_window_start.clear()

    def process_events(self, events: list[DomainEventEnvelopeV1]) -> FeatureTransformResult:
        ordered = sort_events_by_sequence(events)
        result = FeatureTransformResult()
        for event in ordered:
            rejection = self._process_single_event(event)
            if rejection is not None:
                result.rejections.append(rejection)
            result.last_processed_sequence = max(result.last_processed_sequence, event.sequence)
        closed_vectors, closed_windows = self._close_all_open_windows()
        result.vectors.extend(closed_vectors)
        result.windows.extend(closed_windows)
        return result

    def _process_single_event(self, event: DomainEventEnvelopeV1) -> FeatureRejectionV1 | None:
        if event.event_id in self.seen_event_ids:
            return FeatureRejectionV1(
                event_id=event.event_id,
                sequence=event.sequence,
                code=FeatureErrorCode.DUPLICATE_EVENT,
                message=f"Duplicate eventId: {event.event_id}",
            )
        self.seen_event_ids.add(event.event_id)

        rejection = classify_event(event)
        if rejection is not None:
            return rejection

        asset_id = extract_asset_id(event)
        window_start = window_start_epoch(event.sim_time, self.manifest.window_duration_sim_seconds)
        window_key = build_window_key(self.run_id, asset_id, window_start)

        if window_key in self.closed_windows:
            return FeatureRejectionV1(
                event_id=event.event_id,
                sequence=event.sequence,
                code=FeatureErrorCode.LATE_EVENT,
                message=f"Event targets closed window: {window_key}",
            )

        previous_start = self.entity_latest_window_start.get(asset_id)
        if previous_start is not None and window_start > previous_start:
            self._close_entity_windows_before(asset_id, window_start)

        if window_key not in self.open_accumulators:
            start, end = window_bounds(window_start, self.manifest.window_duration_sim_seconds)
            self.open_accumulators[window_key] = WindowAccumulator(
                entity_id=asset_id,
                window_start_epoch=window_start,
                window_start=start,
                window_end=end,
            )
        self.entity_latest_window_start[asset_id] = max(
            self.entity_latest_window_start.get(asset_id, window_start),
            window_start,
        )
        self.open_accumulators[window_key].ingest(event)
        return None

    def _close_entity_windows_before(self, entity_id: str, next_window_start: int) -> None:
        keys_to_close = [
            key
            for key, accumulator in self.open_accumulators.items()
            if accumulator.entity_id == entity_id
            and accumulator.window_start_epoch < next_window_start
        ]
        for key in sorted(keys_to_close):
            self._close_window(key)

    def _close_window(
        self, window_key: str
    ) -> tuple[FeatureVectorV1 | None, FeatureWindowV1 | None]:
        accumulator = self.open_accumulators.pop(window_key, None)
        if accumulator is None or accumulator.telemetry_event_count == 0:
            self.closed_windows.add(window_key)
            return None, None

        vector = self._build_vector(window_key, accumulator)
        window = FeatureWindowV1(
            schema_version=FEATURE_WINDOW_SCHEMA_VERSION,
            window_key=window_key,
            run_id=self.run_id,
            entity_id=accumulator.entity_id,
            window_start_sim_time=accumulator.window_start,
            window_end_sim_time=accumulator.window_end,
            is_closed=True,
            watermark_sequence=accumulator.sequence_end or 0,
        )
        self.closed_windows.add(window_key)
        return vector, window

    def _close_all_open_windows(
        self,
    ) -> tuple[list[FeatureVectorV1], list[FeatureWindowV1]]:
        vectors: list[FeatureVectorV1] = []
        windows: list[FeatureWindowV1] = []
        for key in sorted(self.open_accumulators):
            vector, window = self._close_window(key)
            if vector is not None and window is not None:
                vectors.append(vector)
                windows.append(window)
        vectors.sort(key=lambda item: (item.window_key, item.entity_id))
        windows.sort(key=lambda item: item.window_key)
        return vectors, windows

    def _build_vector(self, window_key: str, accumulator: WindowAccumulator) -> FeatureVectorV1:
        assert accumulator.sequence_start is not None
        assert accumulator.sequence_end is not None
        assert accumulator.sim_time_start is not None
        assert accumulator.sim_time_end is not None
        provenance = FeatureProvenanceV1(
            run_id=self.run_id,
            entity_id=accumulator.entity_id,
            sequence_start=accumulator.sequence_start,
            sequence_end=accumulator.sequence_end,
            sim_time_start=accumulator.sim_time_start,
            sim_time_end=accumulator.sim_time_end,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            transform_version=TRANSFORM_VERSION,
            source_event_ids=list(accumulator.source_event_ids),
        )
        return FeatureVectorV1(
            schema_version=FEATURE_VECTOR_SCHEMA_VERSION,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            window_key=window_key,
            entity_id=accumulator.entity_id,
            values=accumulator_to_values(accumulator),
            provenance=provenance,
        )


def canonical_vectors_json(vectors: list[FeatureVectorV1]) -> str:
    payload = [vector.model_dump(mode="json", by_alias=True) for vector in vectors]
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def checksum_vectors(vectors: list[FeatureVectorV1]) -> str:
    digest = hashlib.sha256(canonical_vectors_json(vectors).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def compute_features_from_events(
    *,
    run_id: str,
    events: list[DomainEventEnvelopeV1],
    manifest: FeatureSchemaManifestV1 = FEATURE_SCHEMA_MANIFEST_V1,
) -> FeatureTransformResult:
    engine = FeatureTransformEngine(manifest=manifest)
    engine.reset(run_id=run_id)
    return engine.process_events(events)


def build_compute_response(result: FeatureTransformResult) -> FeatureComputeResponseV1:
    return FeatureComputeResponseV1(
        schema_version=FEATURE_COMPUTE_RESPONSE_SCHEMA_VERSION,
        vectors=result.vectors,
        windows=result.windows,
        rejections=result.rejections,
        last_processed_sequence=result.last_processed_sequence,
        output_checksum=checksum_vectors(result.vectors),
    )

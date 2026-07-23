"""Phase 13 live command-centre contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aegis_contracts.api import IdempotencyMetadataV1
from aegis_contracts.entities import RunV1
from aegis_contracts.graph import GraphDeltaV1, GraphSnapshotV1
from aegis_contracts.versioning import (
    assert_supported_schema_version,
)


class ConnectionHealthState(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    CATCHING_UP = "catching_up"
    GAP = "gap"
    SNAPSHOT_RESYNC = "snapshot_resync"
    SIMULATOR_PAUSED = "simulator_paused"
    LOCALLY_PAUSED = "locally_paused"
    STALE = "stale"


class TimelineEntryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion")
    sequence: int
    event_id: str = Field(alias="eventId")
    event_type: str = Field(alias="eventType")
    label: str
    timestamp: str
    status: str

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("timeline_entry", value)
        return value


class RunReplicatedState(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion")
    run_id: str = Field(alias="runId")
    last_applied_sequence: int = Field(alias="lastAppliedSequence")
    run_status: str = Field(alias="runStatus")
    sim_time: str = Field(alias="simTime")
    graph_revision: int = Field(alias="graphRevision")
    timeline_entries: list[TimelineEntryV1] = Field(alias="timelineEntries")
    connection_health: ConnectionHealthState = Field(alias="connectionHealth")
    is_stale: bool = Field(alias="isStale")
    locally_paused: bool = Field(alias="locallyPaused")
    seen_event_ids: list[str] = Field(default_factory=list, alias="seenEventIds")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("live_run", value)
        return value


class ApplyGraphDeltaAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["apply_graph_delta"] = "apply_graph_delta"
    delta: GraphDeltaV1


class LoadGraphSnapshotAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["load_graph_snapshot"] = "load_graph_snapshot"
    snapshot: GraphSnapshotV1


class AppendTimelineEntryAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["append_timeline_entry"] = "append_timeline_entry"
    entry: TimelineEntryV1


class UpdateRunStatusAction(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["update_run_status"] = "update_run_status"
    run_status: str = Field(alias="runStatus")
    sim_time: str = Field(alias="simTime")
    sequence: int


class SetConnectionHealthAction(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["set_connection_health"] = "set_connection_health"
    connection_health: ConnectionHealthState = Field(alias="connectionHealth")
    is_stale: bool | None = Field(default=None, alias="isStale")


class MarkGapAction(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["mark_gap"] = "mark_gap"
    expected_sequence: int = Field(alias="expectedSequence")
    received_sequence: int = Field(alias="receivedSequence")


class NoopDuplicateAction(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["noop_duplicate"] = "noop_duplicate"
    event_id: str = Field(alias="eventId")
    sequence: int


class AdvanceSequenceAction(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["advance_sequence"] = "advance_sequence"
    sequence: int
    event_id: str = Field(alias="eventId")


_ReducerActionUnion = (
    ApplyGraphDeltaAction
    | LoadGraphSnapshotAction
    | AppendTimelineEntryAction
    | UpdateRunStatusAction
    | SetConnectionHealthAction
    | MarkGapAction
    | NoopDuplicateAction
    | AdvanceSequenceAction
)

RealtimeReducerAction = Annotated[
    _ReducerActionUnion,
    Field(discriminator="type"),
]


class SnapshotBootstrapPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion")
    run: RunV1
    graph_snapshot: GraphSnapshotV1 = Field(alias="graphSnapshot")
    last_applied_sequence: int = Field(alias="lastAppliedSequence")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("snapshot_bootstrap", value)
        return value


class RunCreateRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion")
    scenario_package_path: str = Field(alias="scenarioPackagePath")
    # Optional: when omitted the API draws a cryptographically random seed in
    # [1, 2^31-1] and persists it (server-side RNG). A supplied seed pins the run
    # deterministically (golden tests always pin their seeds). Additive change —
    # schemaVersion stays 1; existing clients that send a seed are unaffected.
    seed: int | None = None
    run_id: str | None = Field(default=None, alias="runId")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("run_create_request", value)
        return value


class RunCommandResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion")
    run: RunV1
    events_emitted: int = Field(alias="eventsEmitted")
    idempotency: IdempotencyMetadataV1 | None = None

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("run_command_response", value)
        return value


class ConnectionHealthSnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion")
    run_id: str = Field(alias="runId")
    connection_health: ConnectionHealthState = Field(alias="connectionHealth")
    last_applied_sequence: int = Field(alias="lastAppliedSequence")
    is_stale: bool = Field(alias="isStale")
    locally_paused: bool = Field(alias="locallyPaused")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("connection_health", value)
        return value

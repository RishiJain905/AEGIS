"""Phase 26 replay frontend contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import IncidentId, RunId, Sequence, UtcTimestamp
from aegis_contracts.replay import ReplayCursorV1, ReplayErrorCode, ReplayProvenanceV1, StateDiffV1
from aegis_contracts.versioning import (
    HISTORICAL_GRAPH_ADAPTER_SCHEMA_VERSION,
    REPLAY_BOOKMARK_SCHEMA_VERSION,
    REPLAY_COMPARISON_SCHEMA_VERSION,
    REPLAY_VIEW_STATE_SCHEMA_VERSION,
    RETURN_TO_LIVE_RESULT_SCHEMA_VERSION,
    TIMELINE_FILTER_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class ReplayPlaybackSpeedV1(StrEnum):
    HALF = "0.5x"
    ONE = "1x"
    TWO = "2x"
    FOUR = "4x"


class ReplayPlaybackStatusV1(StrEnum):
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"


class ReplayLoadStatusV1(StrEnum):
    IDLE = "idle"
    LOADING = "loading"
    READY = "ready"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class ReplayBookmarkKindV1(StrEnum):
    INCIDENT = "incident"
    SNAPSHOT = "snapshot"
    DETECTION = "detection"
    APPROVAL = "approval"
    REPORT = "report"
    CUSTOM = "custom"


class ReplayViewModeV1(StrEnum):
    HISTORICAL = "historical"
    PLAYBACK = "playback"


class ReplayBookmarkV1(BaseModel):
    """Named jump point for historical scrubbing."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=128)
    run_id: RunId = Field(alias="runId")
    label: str = Field(min_length=1, max_length=256)
    kind: ReplayBookmarkKindV1
    sequence: Sequence
    to_sequence: Sequence | None = Field(default=None, alias="toSequence")
    incident_id: IncidentId | None = Field(default=None, alias="incidentId")
    description: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ReplayBookmarkV1:
        assert_supported_schema_version("replay_bookmark", self.schema_version)
        if self.schema_version != REPLAY_BOOKMARK_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message="Unsupported ReplayBookmark schema version",
                details={"schemaVersion": self.schema_version},
            )
        return self


class TimelineFilterV1(BaseModel):
    """Filter/virtualization controls for the historical timeline."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    event_types: list[str] = Field(default_factory=list, alias="eventTypes")
    incident_id: IncidentId | None = Field(default=None, alias="incidentId")
    query: str | None = Field(default=None, max_length=256)
    from_sequence: Sequence | None = Field(default=None, alias="fromSequence")
    to_sequence: Sequence | None = Field(default=None, alias="toSequence")
    include_bookmarks_only: bool = Field(default=False, alias="includeBookmarksOnly")

    @model_validator(mode="after")
    def validate_schema_and_range(self) -> TimelineFilterV1:
        assert_supported_schema_version("timeline_filter", self.schema_version)
        if self.schema_version != TIMELINE_FILTER_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message="Unsupported TimelineFilter schema version",
                details={"schemaVersion": self.schema_version},
            )
        if (
            self.from_sequence is not None
            and self.to_sequence is not None
            and self.to_sequence < self.from_sequence
        ):
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="toSequence must be >= fromSequence",
                details={
                    "fromSequence": self.from_sequence,
                    "toSequence": self.to_sequence,
                },
            )
        return self


class HistoricalGraphAdapterV1(BaseModel):
    """Serializable binding of reconstructed graph state for historical rendering."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    sequence: Sequence
    graph_revision: int = Field(alias="graphRevision", ge=0)
    state_digest: str = Field(alias="stateDigest", min_length=1, max_length=128)
    source: str = Field(default="replay_state_graph", min_length=1, max_length=64)
    read_only: bool = Field(default=True, alias="readOnly")

    @model_validator(mode="after")
    def validate_schema_version(self) -> HistoricalGraphAdapterV1:
        assert_supported_schema_version("historical_graph_adapter", self.schema_version)
        if self.schema_version != HISTORICAL_GRAPH_ADAPTER_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message="Unsupported HistoricalGraphAdapter schema version",
                details={"schemaVersion": self.schema_version},
            )
        if self.source != "replay_state_graph":
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="HistoricalGraphAdapter source must be replay_state_graph",
                details={"source": self.source},
            )
        if self.read_only is not True:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="HistoricalGraphAdapter must be read-only",
                details={"readOnly": self.read_only},
            )
        return self


class ReplayComparisonV1(BaseModel):
    """Two-cursor comparison view over a StateDiffV1."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    left_sequence: Sequence = Field(alias="leftSequence")
    right_sequence: Sequence = Field(alias="rightSequence")
    left_label: str | None = Field(default=None, alias="leftLabel", max_length=128)
    right_label: str | None = Field(default=None, alias="rightLabel", max_length=128)
    diff: StateDiffV1 | None = None
    loading: bool = False
    error_code: ReplayErrorCode | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage", max_length=512)

    @model_validator(mode="after")
    def validate_schema_and_range(self) -> ReplayComparisonV1:
        assert_supported_schema_version("replay_comparison", self.schema_version)
        if self.schema_version != REPLAY_COMPARISON_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message="Unsupported ReplayComparison schema version",
                details={"schemaVersion": self.schema_version},
            )
        if self.right_sequence < self.left_sequence:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="rightSequence must be >= leftSequence",
                details={
                    "leftSequence": self.left_sequence,
                    "rightSequence": self.right_sequence,
                },
            )
        return self


class ReturnToLiveResultV1(BaseModel):
    """Explicit exit from historical mode requiring authoritative live resync."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    from_sequence: Sequence = Field(alias="fromSequence")
    live_route: str = Field(alias="liveRoute", min_length=1, max_length=512)
    authoritative_resync_required: bool = Field(alias="authoritativeResyncRequired")
    replay_store_cleared: bool = Field(alias="replayStoreCleared")
    completed_at: UtcTimestamp = Field(alias="completedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ReturnToLiveResultV1:
        assert_supported_schema_version("return_to_live_result", self.schema_version)
        if self.schema_version != RETURN_TO_LIVE_RESULT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message="Unsupported ReturnToLiveResult schema version",
                details={"schemaVersion": self.schema_version},
            )
        if self.authoritative_resync_required is not True:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="ReturnToLiveResult must require authoritative resync",
                details={
                    "authoritativeResyncRequired": self.authoritative_resync_required,
                },
            )
        return self


class ReplayViewStateV1(BaseModel):
    """Frontend historical/playback session state (not a reconstruction engine)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    mode: ReplayViewModeV1
    cursor: ReplayCursorV1
    min_sequence: Sequence = Field(alias="minSequence")
    max_sequence: Sequence = Field(alias="maxSequence")
    playback_status: ReplayPlaybackStatusV1 = Field(alias="playbackStatus")
    speed: ReplayPlaybackSpeedV1
    load_status: ReplayLoadStatusV1 = Field(alias="loadStatus")
    reduced_motion: bool = Field(default=False, alias="reducedMotion")
    selected_bookmark_id: str | None = Field(
        default=None, alias="selectedBookmarkId", max_length=128
    )
    timeline_filter: TimelineFilterV1 | None = Field(default=None, alias="timelineFilter")
    comparison: ReplayComparisonV1 | None = None
    historical_graph: HistoricalGraphAdapterV1 | None = Field(
        default=None, alias="historicalGraph"
    )
    provenance: ReplayProvenanceV1 | None = None
    state_digest: str | None = Field(default=None, alias="stateDigest", max_length=128)
    error_code: ReplayErrorCode | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage", max_length=512)
    last_reconstructed_at: UtcTimestamp | None = Field(
        default=None, alias="lastReconstructedAt"
    )

    @model_validator(mode="after")
    def validate_schema_and_cursor(self) -> ReplayViewStateV1:
        assert_supported_schema_version("replay_view_state", self.schema_version)
        if self.schema_version != REPLAY_VIEW_STATE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message="Unsupported ReplayViewState schema version",
                details={"schemaVersion": self.schema_version},
            )
        if self.max_sequence < self.min_sequence:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="maxSequence must be >= minSequence",
                details={
                    "minSequence": self.min_sequence,
                    "maxSequence": self.max_sequence,
                },
            )
        if self.cursor.sequence < self.min_sequence or self.cursor.sequence > self.max_sequence:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="cursor.sequence must be within minSequence..maxSequence",
                details={
                    "cursorSequence": self.cursor.sequence,
                    "minSequence": self.min_sequence,
                    "maxSequence": self.max_sequence,
                },
            )
        return self

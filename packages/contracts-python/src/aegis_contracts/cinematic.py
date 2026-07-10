"""Phase 28 cinematic incident replay contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import IncidentId, RunId, Sequence, SimTimestamp
from aegis_contracts.versioning import (
    CAMERA_DIRECTIVE_SCHEMA_VERSION,
    CINEMATIC_BEAT_SCHEMA_VERSION,
    CINEMATIC_CHAPTER_SCHEMA_VERSION,
    CINEMATIC_PLAN_SCHEMA_VERSION,
    CINEMATIC_PLAYBACK_STATE_SCHEMA_VERSION,
    CINEMATIC_PROVENANCE_SCHEMA_VERSION,
    PRESENTATION_HINT_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class CinematicErrorCode(StrEnum):
    CINEMATIC_VALIDATION_FAILED = "CINEMATIC_VALIDATION_FAILED"
    CINEMATIC_INCOMPATIBLE = "CINEMATIC_INCOMPATIBLE"
    CINEMATIC_MISSING_REFERENCE = "CINEMATIC_MISSING_REFERENCE"
    CINEMATIC_HINT_BLOCKED = "CINEMATIC_HINT_BLOCKED"
    CINEMATIC_REPLAY_UNAVAILABLE = "CINEMATIC_REPLAY_UNAVAILABLE"


class CinematicBeatKindV1(StrEnum):
    ESTABLISHING = "establishing"
    INCIDENT_ORIGIN = "incident_origin"
    EVIDENCE_FOCUS = "evidence_focus"
    PATH_TRACE = "path_trace"
    AGENT_INVESTIGATION = "agent_investigation"
    RISK_CHANGE = "risk_change"
    PROPOSAL_FOCUS = "proposal_focus"
    APPROVAL_MOMENT = "approval_moment"
    CONSEQUENCE_REVEAL = "consequence_reveal"
    REPORT_FOCUS = "report_focus"
    OVERVIEW = "overview"


class CameraDirectiveKindV1(StrEnum):
    ESTABLISHING = "establishing"
    ENTITY_FOCUS = "entity_focus"
    PATH_TRACE = "path_trace"
    AGENT_FOCUS = "agent_focus"
    APPROVAL = "approval"
    CONSEQUENCE = "consequence"
    OVERVIEW = "overview"


class CinematicProvenanceSourceV1(StrEnum):
    REPLAY_STATE = "replay_state"
    PRESENTATION_HINT = "presentation_hint"
    DEFAULT_PLANNER = "default_planner"


class PresentationHintKindV1(StrEnum):
    EMPHASIS = "emphasis"
    CHAPTER_ANCHOR = "chapter_anchor"
    CAPTION = "caption"


class CinematicSessionModeV1(StrEnum):
    NORMAL = "normal"
    CINEMATIC = "cinematic"


class CinematicDirectorStatusV1(StrEnum):
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    FREE_CAMERA = "free_camera"


class CinematicPlaybackSpeedV1(StrEnum):
    HALF = "0.5x"
    ONE = "1x"
    TWO = "2x"
    FOUR = "4x"


class Vec3WireV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    z: float


class CameraBookmarkWireV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    position: Vec3WireV1
    target: Vec3WireV1
    fov: float = Field(gt=0)


class CinematicProvenanceV1(BaseModel):
    """Links a cinematic beat to authoritative replay cursor/entity provenance."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    sequence: Sequence
    sim_time: SimTimestamp | None = Field(default=None, alias="simTime")
    entity_ids: list[str] = Field(default_factory=list, alias="entityIds")
    incident_id: IncidentId | None = Field(default=None, alias="incidentId")
    source: CinematicProvenanceSourceV1
    state_digest: str | None = Field(default=None, alias="stateDigest", max_length=128)

    @model_validator(mode="after")
    def validate_schema_version(self) -> CinematicProvenanceV1:
        assert_supported_schema_version("cinematic_provenance", self.schema_version)
        if self.schema_version != CINEMATIC_PROVENANCE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message="Unsupported CinematicProvenance schema version",
                details={"schemaVersion": self.schema_version},
            )
        return self


class CameraDirectiveV1(BaseModel):
    """Presentation-only camera instruction; never mutates domain state."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=128)
    kind: CameraDirectiveKindV1
    focus_entity_ids: list[str] = Field(default_factory=list, alias="focusEntityIds")
    path_entity_ids: list[str] = Field(default_factory=list, alias="pathEntityIds")
    bookmark: CameraBookmarkWireV1 | None = None
    transition_ms: int = Field(default=800, alias="transitionMs", ge=0, le=30_000)
    reduced_motion_jump: bool = Field(default=True, alias="reducedMotionJump")

    @model_validator(mode="after")
    def validate_schema_version(self) -> CameraDirectiveV1:
        assert_supported_schema_version("camera_directive", self.schema_version)
        if self.schema_version != CAMERA_DIRECTIVE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message="Unsupported CameraDirective schema version",
                details={"schemaVersion": self.schema_version},
            )
        return self


class CinematicBeatV1(BaseModel):
    """One directed cinematic moment tied to an authoritative replay sequence."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=128)
    chapter_id: str = Field(alias="chapterId", min_length=1, max_length=128)
    kind: CinematicBeatKindV1
    sequence: Sequence
    sim_time: SimTimestamp | None = Field(default=None, alias="simTime")
    caption: str = Field(min_length=1, max_length=512)
    entity_ids: list[str] = Field(default_factory=list, alias="entityIds")
    path_entity_ids: list[str] = Field(default_factory=list, alias="pathEntityIds")
    camera_directive_id: str = Field(alias="cameraDirectiveId", min_length=1, max_length=128)
    provenance: CinematicProvenanceV1
    priority: int = Field(default=100, ge=0, le=1000)
    tie_breaker: int = Field(default=0, alias="tieBreaker", ge=0, le=1_000_000)

    @model_validator(mode="after")
    def validate_schema_version(self) -> CinematicBeatV1:
        assert_supported_schema_version("cinematic_beat", self.schema_version)
        if self.schema_version != CINEMATIC_BEAT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message="Unsupported CinematicBeat schema version",
                details={"schemaVersion": self.schema_version},
            )
        return self


class CinematicChapterV1(BaseModel):
    """Ordered chapter spanning a sequence range over authoritative replay."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    summary: str = Field(min_length=1, max_length=512)
    from_sequence: Sequence = Field(alias="fromSequence")
    to_sequence: Sequence = Field(alias="toSequence")
    beat_ids: list[str] = Field(default_factory=list, alias="beatIds")
    order: int = Field(ge=0, le=1000)

    @model_validator(mode="after")
    def validate_schema_and_range(self) -> CinematicChapterV1:
        assert_supported_schema_version("cinematic_chapter", self.schema_version)
        if self.schema_version != CINEMATIC_CHAPTER_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message="Unsupported CinematicChapter schema version",
                details={"schemaVersion": self.schema_version},
            )
        if self.to_sequence < self.from_sequence:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="toSequence must be >= fromSequence",
                details={
                    "fromSequence": self.from_sequence,
                    "toSequence": self.to_sequence,
                },
            )
        return self


class PresentationHintV1(BaseModel):
    """Safe scenario presentation hint. Must not reveal hidden causes."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=128)
    scenario_id: str = Field(alias="scenarioId", min_length=1, max_length=128)
    kind: PresentationHintKindV1
    sequence: Sequence
    entity_ids: list[str] = Field(default_factory=list, alias="entityIds")
    caption: str | None = Field(default=None, max_length=512)
    chapter_id: str | None = Field(default=None, alias="chapterId", max_length=128)
    requires_evidence_ids: list[str] = Field(
        default_factory=list, alias="requiresEvidenceIds"
    )
    reveals_hidden_cause: bool = Field(default=False, alias="revealsHiddenCause")
    hidden_cause_id: str | None = Field(default=None, alias="hiddenCauseId", max_length=128)

    @model_validator(mode="after")
    def validate_schema_and_safety(self) -> PresentationHintV1:
        assert_supported_schema_version("presentation_hint", self.schema_version)
        if self.schema_version != PRESENTATION_HINT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message="Unsupported PresentationHint schema version",
                details={"schemaVersion": self.schema_version},
            )
        if self.reveals_hidden_cause is not False:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="Presentation hints must not reveal hidden causes",
                details={"revealsHiddenCause": self.reveals_hidden_cause},
            )
        if self.hidden_cause_id is not None:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="hiddenCauseId is forbidden on safe presentation hints",
                details={"hiddenCauseId": self.hidden_cause_id},
            )
        return self


class CinematicPlaybackStateV1(BaseModel):
    """Ephemeral cinematic director session state (presentation only)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    mode: CinematicSessionModeV1
    status: CinematicDirectorStatusV1
    chapter_index: int = Field(alias="chapterIndex", ge=0)
    beat_index: int = Field(alias="beatIndex", ge=0)
    speed: CinematicPlaybackSpeedV1
    reduced_motion: bool = Field(default=False, alias="reducedMotion")
    captions_enabled: bool = Field(default=True, alias="captionsEnabled")
    active_beat_id: str | None = Field(default=None, alias="activeBeatId", max_length=128)
    active_chapter_id: str | None = Field(
        default=None, alias="activeChapterId", max_length=128
    )

    @model_validator(mode="after")
    def validate_schema_version(self) -> CinematicPlaybackStateV1:
        assert_supported_schema_version("cinematic_playback_state", self.schema_version)
        if self.schema_version != CINEMATIC_PLAYBACK_STATE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message="Unsupported CinematicPlaybackState schema version",
                details={"schemaVersion": self.schema_version},
            )
        return self


class CinematicPlanV1(BaseModel):
    """Deterministic cinematic plan derived from authoritative replay state."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    chapters: list[CinematicChapterV1] = Field(min_length=1)
    beats: list[CinematicBeatV1] = Field(min_length=1)
    camera_directives: list[CameraDirectiveV1] = Field(
        min_length=1, alias="cameraDirectives"
    )
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_schema_version(self) -> CinematicPlanV1:
        assert_supported_schema_version("cinematic_plan", self.schema_version)
        if self.schema_version != CINEMATIC_PLAN_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message="Unsupported CinematicPlan schema version",
                details={"schemaVersion": self.schema_version},
            )
        return self

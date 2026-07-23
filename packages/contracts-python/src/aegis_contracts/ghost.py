"""Ghost branch — post-run counterfactual replay contracts.

The flagship after-action capability. Once a run is terminal, the operator picks a real
decision point (an executed containment action, or a salient "inaction window") and asks
"what if I had done X instead / earlier / nothing?". A dedicated deterministic engine
re-simulates the scenario from that point with the alternate decision, entirely in-memory
and isolated from the real run's event stream, and returns the REAL alternate timeline —
not speculation.

These contracts are additive and post-run only. Nothing here writes to the run; the ghost
engine reads persisted events and reconstructs a throwaway runtime.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import AssetId, RunId
from aegis_contracts.proposals import ScenarioCommandTemplateV1
from aegis_contracts.versioning import (
    GHOST_BRANCH_REQUEST_SCHEMA_VERSION,
    GHOST_BRANCH_RESULT_SCHEMA_VERSION,
    GHOST_DECISION_POINT_SCHEMA_VERSION,
    GHOST_DECISION_POINTS_SCHEMA_VERSION,
    assert_supported_schema_version,
)

__all__ = [
    "GhostAssetDiffV1",
    "GhostBranchModeV1",
    "GhostBranchRequestV1",
    "GhostBranchResultV1",
    "GhostDecisionKindV1",
    "GhostDecisionPointV1",
    "GhostDecisionPointsV1",
    "GhostOutcomeV1",
    "GhostTimelineBeatV1",
]

# A single re-simulation is bounded; a shift cannot move the decision more than this many
# sim-seconds in either direction (keeps the counterfactual anchored near the real moment).
MAX_SHIFT_SIM_SECONDS = 3600


class GhostDecisionKindV1(StrEnum):
    """What a decision point represents in the real run."""

    EXECUTED_ACTION = "executed_action"
    INACTION_WINDOW = "inaction_window"


class GhostBranchModeV1(StrEnum):
    """How the operator's real decision is altered in the counterfactual."""

    # Replace the real command with a different allowlisted command (optionally on a
    # different target). For an inaction window, this injects an action where there was none.
    SUBSTITUTE = "substitute"
    # Remove the real action entirely — "what if I had done nothing here?".
    DO_NOTHING = "do_nothing"
    # Keep the real command but apply it earlier/later by ``shift_sim_seconds``.
    SHIFT = "shift"


class GhostDecisionPointV1(BaseModel):
    """One real decision the operator can fork from in the after-action ghost panel."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    # Stable, deterministic reference derived from the real event stream, e.g.
    # ``execact:<sequence>`` or ``inaction:<sequence>``.
    decision_ref: str = Field(alias="decisionRef", min_length=1, max_length=128)
    kind: GhostDecisionKindV1
    sequence: int = Field(ge=0)
    sim_time: str = Field(alias="simTime")
    # The real command executed at this point (null for an inaction window).
    scenario_command: ScenarioCommandTemplateV1 | None = Field(
        default=None, alias="scenarioCommand"
    )
    target_asset_id: str | None = Field(default=None, alias="targetAssetId")
    action_class: str | None = Field(default=None, alias="actionClass")
    label: str

    @model_validator(mode="after")
    def validate_schema_version(self) -> GhostDecisionPointV1:
        assert_supported_schema_version("ghost_decision_point", self.schema_version)
        if self.schema_version != GHOST_DECISION_POINT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported ghost decision point schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class GhostDecisionPointsV1(BaseModel):
    """The enumerated fork points for a terminal run (GET response)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    decision_points: list[GhostDecisionPointV1] = Field(
        default_factory=list, alias="decisionPoints"
    )

    @model_validator(mode="after")
    def validate_schema_version(self) -> GhostDecisionPointsV1:
        assert_supported_schema_version("ghost_decision_points", self.schema_version)
        if self.schema_version != GHOST_DECISION_POINTS_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported ghost decision points schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class GhostBranchRequestV1(BaseModel):
    """Ask the engine to re-simulate one decision differently (POST body)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    decision_ref: str = Field(alias="decisionRef", min_length=1, max_length=128)
    mode: GhostBranchModeV1
    # SUBSTITUTE only: the alternate command (required) and optional alternate target
    # (defaults to the real decision's target).
    alternate_command: ScenarioCommandTemplateV1 | None = Field(
        default=None, alias="alternateCommand"
    )
    alternate_target_asset_id: AssetId | None = Field(
        default=None, alias="alternateTargetAssetId"
    )
    # SHIFT only: negative applies the real command earlier, positive later.
    shift_sim_seconds: int | None = Field(default=None, alias="shiftSimSeconds")

    @model_validator(mode="after")
    def validate_request(self) -> GhostBranchRequestV1:
        assert_supported_schema_version("ghost_branch_request", self.schema_version)
        if self.schema_version != GHOST_BRANCH_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported ghost branch request schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        if self.mode == GhostBranchModeV1.SUBSTITUTE and self.alternate_command is None:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message="substitute mode requires alternateCommand",
                details={"mode": self.mode.value},
            )
        if self.mode == GhostBranchModeV1.SHIFT:
            if self.shift_sim_seconds is None or self.shift_sim_seconds == 0:
                raise ContractValidationError(
                    code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                    message="shift mode requires a non-zero shiftSimSeconds",
                    details={"mode": self.mode.value},
                )
            if abs(self.shift_sim_seconds) > MAX_SHIFT_SIM_SECONDS:
                raise ContractValidationError(
                    code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                    message=f"shiftSimSeconds exceeds +/-{MAX_SHIFT_SIM_SECONDS}",
                    details={"shiftSimSeconds": self.shift_sim_seconds},
                )
        return self


class GhostTimelineBeatV1(BaseModel):
    """One attacker/simulation beat on the ghost timeline after the divergence."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    sequence: int = Field(ge=0)
    sim_time: str = Field(alias="simTime")
    # "asset_status" | "condition_triggered" | "condition_revealed" | "branch_selected".
    kind: str
    label: str
    asset_id: str | None = Field(default=None, alias="assetId")
    status: str | None = None


class GhostAssetStatusV1(BaseModel):
    """A single asset's final status in one timeline."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    asset_id: str = Field(alias="assetId")
    status: str


class GhostOutcomeV1(BaseModel):
    """The terminal-state summary of one timeline (real or ghost)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    # "real" | "ghost".
    label: str
    final_statuses: list[GhostAssetStatusV1] = Field(
        default_factory=list, alias="finalStatuses"
    )
    compromised_count: int = Field(alias="compromisedCount", ge=0)
    contained_count: int = Field(alias="containedCount", ge=0)
    # A breach occurred when the adversary drove any asset to a compromised terminal state.
    breach_occurred: bool = Field(alias="breachOccurred")
    breach_asset_ids: list[str] = Field(default_factory=list, alias="breachAssetIds")


class GhostAssetDiffV1(BaseModel):
    """An asset whose final status differs between the real and ghost timelines."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    asset_id: str = Field(alias="assetId")
    real_status: str = Field(alias="realStatus")
    ghost_status: str = Field(alias="ghostStatus")


class GhostBranchResultV1(BaseModel):
    """The counterfactual result (POST response) — real vs ghost, diffs, timeline, verdict."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    decision_ref: str = Field(alias="decisionRef")
    mode: GhostBranchModeV1
    # Deterministic hash of the normalized request — the cache/identity key.
    request_fingerprint: str = Field(alias="requestFingerprint")
    # Deterministic hash of the ghost outcome — identical requests produce identical hashes.
    result_hash: str = Field(alias="resultHash")
    divergence_sequence: int = Field(alias="divergenceSequence", ge=0)
    divergence_sim_time: str = Field(alias="divergenceSimTime")
    steps_simulated: int = Field(alias="stepsSimulated", ge=0)
    real_outcome: GhostOutcomeV1 = Field(alias="realOutcome")
    ghost_outcome: GhostOutcomeV1 = Field(alias="ghostOutcome")
    asset_diffs: list[GhostAssetDiffV1] = Field(default_factory=list, alias="assetDiffs")
    ghost_timeline: list[GhostTimelineBeatV1] = Field(
        default_factory=list, alias="ghostTimeline"
    )
    # The real run's stored overall score, for context. There is deliberately no ghost score:
    # rubric scoring reads persisted DB facts and cannot be recomputed without persisting
    # ghost artifacts, so surfacing a fabricated number would be dishonest.
    real_overall_score: float | None = Field(default=None, alias="realOverallScore")
    verdict: str

    @model_validator(mode="after")
    def validate_schema_version(self) -> GhostBranchResultV1:
        assert_supported_schema_version("ghost_branch_result", self.schema_version)
        if self.schema_version != GHOST_BRANCH_RESULT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported ghost branch result schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self

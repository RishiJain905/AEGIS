"""Scenario manifest semantic validation."""

from __future__ import annotations

from collections.abc import Callable

from aegis_scenario_sdk.compatibility import is_platform_version_compatible
from aegis_scenario_sdk.contracts.manifest import ScenarioManifestV1
from aegis_scenario_sdk.diagnostics import ValidationDiagnostic
from aegis_scenario_sdk.errors import ScenarioErrorCode
from aegis_scenario_sdk.plugins.registry import is_known_plugin, validate_plugin_config
from aegis_scenario_sdk.validation.safety import validate_media_path


def _append_duplicate(
    diagnostics: list[ValidationDiagnostic],
    *,
    path: str,
    identifier: str,
) -> None:
    diagnostics.append(
        ValidationDiagnostic(
            code=ScenarioErrorCode.DUPLICATE_ID,
            path=path,
            message=f"Duplicate identifier: {identifier}",
            details={"id": identifier},
        )
    )


def validate_semantics(manifest: ScenarioManifestV1) -> list[ValidationDiagnostic]:
    diagnostics: list[ValidationDiagnostic] = []

    if not is_platform_version_compatible(manifest.metadata.required_platform_version):
        diagnostics.append(
            ValidationDiagnostic(
                code=ScenarioErrorCode.PLATFORM_VERSION_INCOMPATIBLE,
                path="metadata.requiredPlatformVersion",
                message=(
                    "Scenario requires a newer platform version: "
                    f"{manifest.metadata.required_platform_version}"
                ),
                details={"requiredPlatformVersion": manifest.metadata.required_platform_version},
            )
        )

    seen_ids: dict[str, str] = {}

    def track(identifier: str, path: str) -> None:
        if identifier in seen_ids:
            _append_duplicate(diagnostics, path=path, identifier=identifier)
        else:
            seen_ids[identifier] = path

    zone_ids = {zone.id for zone in manifest.zones}
    for index, zone in enumerate(manifest.zones):
        track(zone.id, f"zones[{index}].id")

    asset_ids: set[str] = set()
    for index, asset in enumerate(manifest.assets):
        track(asset.id, f"assets[{index}].id")
        asset_ids.add(asset.id)
        if asset.zone_id not in zone_ids:
            diagnostics.append(
                ValidationDiagnostic(
                    code=ScenarioErrorCode.DANGLING_REFERENCE,
                    path=f"assets[{index}].zoneId",
                    message=f"Unknown zone reference: {asset.zone_id}",
                    details={"zoneId": asset.zone_id},
                )
            )

    local_ids: set[str] = set()
    for index, generator in enumerate(manifest.generators):
        track(generator.id, f"generators[{index}].id")
        local_ids.add(generator.id)
        if generator.target_asset_id not in asset_ids:
            diagnostics.append(
                ValidationDiagnostic(
                    code=ScenarioErrorCode.DANGLING_REFERENCE,
                    path=f"generators[{index}].targetAssetId",
                    message=f"Unknown asset reference: {generator.target_asset_id}",
                    details={"targetAssetId": generator.target_asset_id},
                )
            )
        _validate_plugin(diagnostics, generator.plugin, f"generators[{index}].plugin")

    for index, event in enumerate(manifest.scheduled_events):
        track(event.id, f"scheduledEvents[{index}].id")
        local_ids.add(event.id)
        _validate_plugin(diagnostics, event.action, f"scheduledEvents[{index}].action")
        if event.branch_gate is not None:
            gate = event.branch_gate
            branch_ids = {branch.id for branch in manifest.branches}
            if gate.branch_id not in branch_ids:
                diagnostics.append(
                    ValidationDiagnostic(
                        code=ScenarioErrorCode.DANGLING_REFERENCE,
                        path=f"scheduledEvents[{index}].branchGate.branchId",
                        message=f"Unknown branch gate reference: {gate.branch_id}",
                        details={"branchId": gate.branch_id},
                    )
                )

    for index, condition in enumerate(manifest.hidden_conditions):
        track(condition.id, f"hiddenConditions[{index}].id")
        local_ids.add(condition.id)
        for ref_index, ref in enumerate(condition.trigger_refs):
            if ref not in local_ids and ref not in asset_ids:
                diagnostics.append(
                    ValidationDiagnostic(
                        code=ScenarioErrorCode.DANGLING_REFERENCE,
                        path=f"hiddenConditions[{index}].triggerRefs[{ref_index}]",
                        message=f"Unknown trigger reference: {ref}",
                        details={"ref": ref},
                    )
                )
        for ref_index, ref in enumerate(condition.effect_refs):
            if ref not in local_ids:
                diagnostics.append(
                    ValidationDiagnostic(
                        code=ScenarioErrorCode.DANGLING_REFERENCE,
                        path=f"hiddenConditions[{index}].effectRefs[{ref_index}]",
                        message=f"Unknown effect reference: {ref}",
                        details={"ref": ref},
                    )
                )

    branch_weight_by_group: dict[str, float] = {}
    for index, branch in enumerate(manifest.branches):
        track(branch.id, f"branches[{index}].id")
        local_ids.add(branch.id)
        group = branch.branch_group or "__default__"
        branch_weight_by_group[group] = branch_weight_by_group.get(group, 0.0) + branch.weight
        if branch.weight < 0.0 or branch.weight > 1.0:
            diagnostics.append(
                ValidationDiagnostic(
                    code=ScenarioErrorCode.INVALID_BRANCH_WEIGHT,
                    path=f"branches[{index}].weight",
                    message="Branch weight must be between 0 and 1",
                    details={"weight": branch.weight},
                )
            )
        for outcome_index, outcome in enumerate(branch.outcomes):
            if outcome.target_ref not in local_ids and outcome.target_ref not in asset_ids:
                diagnostics.append(
                    ValidationDiagnostic(
                        code=ScenarioErrorCode.DANGLING_REFERENCE,
                        path=f"branches[{index}].outcomes[{outcome_index}].targetRef",
                        message=f"Unknown branch outcome reference: {outcome.target_ref}",
                        details={"targetRef": outcome.target_ref},
                    )
                )

    for group, total_weight in branch_weight_by_group.items():
        if total_weight > 1.0 + 1e-9:
            diagnostics.append(
                ValidationDiagnostic(
                    code=ScenarioErrorCode.INVALID_BRANCH_WEIGHT,
                    path="branches",
                    message=(
                        f"Branch weights for group {group!r} must not exceed 1.0 in aggregate"
                    ),
                    details={"branchGroup": group, "totalWeight": total_weight},
                )
            )

    _validate_campaigns(manifest, diagnostics, track, asset_ids)

    for index, objective in enumerate(manifest.objectives):
        track(objective.id, f"objectives[{index}].id")
        local_ids.add(objective.id)

    scoring_weight_total = sum(criterion.weight for criterion in manifest.scoring.criteria)
    if scoring_weight_total <= 0.0:
        diagnostics.append(
            ValidationDiagnostic(
                code=ScenarioErrorCode.VALIDATION_FAILED,
                path="scoring.criteria",
                message="Scoring criteria weights must sum to a positive value",
                details={"totalWeight": scoring_weight_total},
            )
        )

    for index, relationship in enumerate(manifest.relationships):
        track(relationship.id, f"relationships[{index}].id")
        if relationship.source not in asset_ids:
            diagnostics.append(
                ValidationDiagnostic(
                    code=ScenarioErrorCode.DANGLING_REFERENCE,
                    path=f"relationships[{index}].source",
                    message=f"Unknown source asset: {relationship.source}",
                    details={"source": relationship.source},
                )
            )
        if relationship.target not in asset_ids:
            diagnostics.append(
                ValidationDiagnostic(
                    code=ScenarioErrorCode.DANGLING_REFERENCE,
                    path=f"relationships[{index}].target",
                    message=f"Unknown target asset: {relationship.target}",
                    details={"target": relationship.target},
                )
            )

    for index, media in enumerate(manifest.media):
        track(media.id, f"media[{index}].id")
        media_issue = validate_media_path(media.path, f"media[{index}].path")
        if media_issue is not None:
            diagnostics.append(media_issue)

    return diagnostics


def _dangling(
    diagnostics: list[ValidationDiagnostic],
    *,
    path: str,
    message: str,
    details: dict[str, object],
) -> None:
    diagnostics.append(
        ValidationDiagnostic(
            code=ScenarioErrorCode.DANGLING_REFERENCE,
            path=path,
            message=message,
            details=details,
        )
    )


def _validate_anchor(
    diagnostics: list[ValidationDiagnostic],
    anchor: object,
    path: str,
    asset_ids: set[str],
) -> None:
    from aegis_scenario_sdk.contracts.manifest import AnchorSelectorMode

    mode = getattr(anchor, "mode", None)
    asset_id = getattr(anchor, "asset_id", None)
    from_asset_id = getattr(anchor, "from_asset_id", None)
    relationship_type = getattr(anchor, "relationship_type", None)
    if mode == AnchorSelectorMode.BY_ID and (asset_id is None or asset_id not in asset_ids):
        _dangling(
            diagnostics,
            path=f"{path}.assetId",
            message=f"Anchor by_id references unknown asset: {asset_id}",
            details={"assetId": asset_id},
        )
    if mode == AnchorSelectorMode.ALONG_EDGE and relationship_type is None:
        diagnostics.append(
            ValidationDiagnostic(
                code=ScenarioErrorCode.VALIDATION_FAILED,
                path=f"{path}.relationshipType",
                message="Anchor along_edge requires a relationshipType",
                details={},
            )
        )
    if from_asset_id is not None and from_asset_id not in asset_ids:
        _dangling(
            diagnostics,
            path=f"{path}.fromAssetId",
            message=f"Anchor fromAssetId references unknown asset: {from_asset_id}",
            details={"fromAssetId": from_asset_id},
        )


def _validate_campaigns(
    manifest: ScenarioManifestV1,
    diagnostics: list[ValidationDiagnostic],
    track: Callable[[str, str], None],
    asset_ids: set[str],
) -> None:
    branch_ids = {branch.id for branch in manifest.branches}
    for index, campaign in enumerate(manifest.campaigns):
        track(campaign.id, f"campaigns[{index}].id")
        if campaign.bound_branch_id not in branch_ids:
            _dangling(
                diagnostics,
                path=f"campaigns[{index}].boundBranchId",
                message=f"Campaign bound to unknown branch: {campaign.bound_branch_id}",
                details={"boundBranchId": campaign.bound_branch_id},
            )
        _validate_anchor(
            diagnostics, campaign.entry_anchor, f"campaigns[{index}].entryAnchor", asset_ids
        )
        technique_ids: set[str] = set()
        for t_index, technique in enumerate(campaign.techniques):
            t_path = f"campaigns[{index}].techniques[{t_index}]"
            if technique.id in technique_ids:
                _append_duplicate(diagnostics, path=f"{t_path}.id", identifier=technique.id)
            technique_ids.add(technique.id)
            _validate_anchor(diagnostics, technique.anchor, f"{t_path}.anchor", asset_ids)
            for s_index, signal in enumerate(technique.signals):
                _validate_plugin(diagnostics, signal.plugin, f"{t_path}.signals[{s_index}].plugin")
        for r_index, reaction in enumerate(campaign.reactions):
            r_path = f"campaigns[{index}].reactions[{r_index}]"
            move = reaction.counter_move
            if move.technique_id is not None and move.technique_id not in technique_ids:
                _dangling(
                    diagnostics,
                    path=f"{r_path}.counterMove.techniqueId",
                    message=f"Reaction references unknown technique: {move.technique_id}",
                    details={"techniqueId": move.technique_id},
                )
            if move.asset_id is not None and move.asset_id not in asset_ids:
                _dangling(
                    diagnostics,
                    path=f"{r_path}.counterMove.assetId",
                    message=f"Reaction pivot references unknown asset: {move.asset_id}",
                    details={"assetId": move.asset_id},
                )
            if reaction.precondition.asset_id is not None and (
                reaction.precondition.asset_id not in asset_ids
            ):
                _dangling(
                    diagnostics,
                    path=f"{r_path}.precondition.assetId",
                    message=f"Reaction precondition references unknown asset: "
                    f"{reaction.precondition.asset_id}",
                    details={"assetId": reaction.precondition.asset_id},
                )


def _validate_plugin(
    diagnostics: list[ValidationDiagnostic],
    plugin: object,
    path: str,
) -> None:
    plugin_id = getattr(plugin, "plugin_id", None)
    config = getattr(plugin, "config", {})
    if not isinstance(plugin_id, str):
        return
    if not is_known_plugin(plugin_id):
        diagnostics.append(
            ValidationDiagnostic(
                code=ScenarioErrorCode.UNKNOWN_PLUGIN,
                path=f"{path}.pluginId",
                message=f"Unknown behavior plugin: {plugin_id}",
                details={"pluginId": plugin_id},
            )
        )
        return
    error = validate_plugin_config(plugin_id, config)
    if error is not None:
        diagnostics.append(
            ValidationDiagnostic(
                code=ScenarioErrorCode.INVALID_PLUGIN_CONFIG,
                path=f"{path}.config",
                message=error,
                details={"pluginId": plugin_id},
            )
        )

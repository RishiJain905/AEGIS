#!/usr/bin/env python3
# ruff: noqa: E501
"""Generate Operation Silent Relay manifest.yaml for Phase 10."""

from __future__ import annotations

from pathlib import Path

import yaml

OUTPUT = Path(__file__).resolve().parents[1] / "scenarios" / "operation-silent-relay" / "manifest.yaml"

ZONES = [
    {"id": "business-unit:logistics", "label": "Logistics Operations", "securityLevel": "standard"},
    {"id": "business-unit:communications", "label": "Communications", "securityLevel": "elevated"},
    {"id": "business-unit:identity", "label": "Identity and Access", "securityLevel": "elevated"},
    {"id": "business-unit:cloud", "label": "Cloud Platform", "securityLevel": "standard"},
    {"id": "business-unit:endpoints", "label": "Endpoints", "securityLevel": "standard"},
    {"id": "business-unit:data-platform", "label": "Data Platform", "securityLevel": "elevated"},
    {"id": "business-unit:security-ops", "label": "Security Operations", "securityLevel": "restricted"},
    {"id": "business-unit:ai-ops", "label": "AI Operations", "securityLevel": "elevated"},
]

ASSETS = [
    ("asset:svc-logistics-api", "service", "Logistics Routing API", "business-unit:logistics", 0.93, 0.12),
    ("asset:svc-fleet-coordinator", "service", "Fleet Coordinator", "business-unit:logistics", 0.85, 0.1),
    ("asset:svc-shipment-scheduler", "service", "Shipment Scheduler", "business-unit:logistics", 0.82, 0.08),
    ("asset:svc-route-optimizer", "service", "Route Optimizer", "business-unit:logistics", 0.8, 0.07),
    ("asset:device-dispatch-terminal", "device", "Dispatch Terminal", "business-unit:logistics", 0.55, 0.05),
    ("asset:svc-comms-gateway", "service", "Communications Gateway", "business-unit:communications", 0.9, 0.1),
    ("asset:svc-message-bus", "service", "Message Bus", "business-unit:communications", 0.78, 0.08),
    ("asset:svc-notification-service", "service", "Notification Service", "business-unit:communications", 0.7, 0.06),
    ("asset:svc-email-relay", "service", "Email Relay", "business-unit:communications", 0.65, 0.05),
    ("asset:svc-identity-broker", "service", "Identity Broker", "business-unit:identity", 0.96, 0.08),
    ("asset:svc-sso-broker", "service", "SSO Broker", "business-unit:identity", 0.92, 0.07),
    ("asset:svc-service-account-vault", "service", "Service Account Vault", "business-unit:identity", 0.94, 0.06),
    ("asset:identity-svc-logistics-bot", "identity", "Logistics Service Bot", "business-unit:identity", 0.75, 0.15),
    ("asset:svc-k8s-control-plane", "service", "Kubernetes Control Plane", "business-unit:cloud", 0.95, 0.1),
    ("asset:svc-cicd-pipeline", "service", "CI/CD Pipeline", "business-unit:cloud", 0.88, 0.09),
    ("asset:svc-container-registry", "service", "Container Registry", "business-unit:cloud", 0.86, 0.08),
    ("asset:svc-cloud-config", "service", "Cloud Config Service", "business-unit:cloud", 0.8, 0.07),
    ("asset:svc-secrets-manager", "service", "Secrets Manager", "business-unit:cloud", 0.91, 0.05),
    ("asset:device-analyst-01", "device", "SOC Analyst Workstation", "business-unit:endpoints", 0.5, 0.02),
    ("asset:device-field-tablet-02", "device", "Field Operations Tablet", "business-unit:endpoints", 0.45, 0.03),
    ("asset:device-vendor-vpn-03", "device", "Vendor VPN Client", "business-unit:endpoints", 0.6, 0.2),
    ("asset:device-ops-jumphost", "device", "Operations Jumphost", "business-unit:endpoints", 0.7, 0.1),
    ("asset:database-audit-store", "database", "Audit Store", "business-unit:data-platform", 0.88, 0.05),
    ("asset:database-customer-pii", "database", "Customer PII Database", "business-unit:data-platform", 0.94, 0.08),
    ("asset:database-analytics-warehouse", "database", "Analytics Warehouse", "business-unit:data-platform", 0.8, 0.06),
    ("asset:database-shipment-records", "database", "Shipment Records DB", "business-unit:data-platform", 0.85, 0.07),
    ("asset:svc-siem-forwarder", "service", "SIEM Forwarder", "business-unit:security-ops", 0.87, 0.04),
    ("asset:svc-edr-console", "service", "EDR Console", "business-unit:security-ops", 0.83, 0.05),
    ("asset:svc-vuln-scanner", "service", "Vulnerability Scanner", "business-unit:security-ops", 0.7, 0.03),
    ("asset:control-soc-playbook-runner", "control", "SOC Playbook Runner", "business-unit:security-ops", 0.75, 0.04),
    ("asset:svc-routing-inference-gateway", "service", "Routing Inference Gateway", "business-unit:ai-ops", 0.84, 0.09),
    ("asset:svc-model-registry", "service", "Model Registry", "business-unit:ai-ops", 0.78, 0.06),
    ("asset:svc-feature-store", "service", "Feature Store", "business-unit:ai-ops", 0.76, 0.05),
    ("asset:ai-model-logistics-router", "ai_model", "Logistics Router Model", "business-unit:ai-ops", 0.82, 0.08),
    ("asset:user-ciso", "user", "Chief Information Security Officer", "business-unit:security-ops", 0.4, 0.0),
    ("asset:user-logistics-admin", "user", "Logistics Administrator", "business-unit:logistics", 0.5, 0.05),
    ("asset:user-devops-lead", "user", "DevOps Lead", "business-unit:cloud", 0.55, 0.04),
    ("asset:user-contractor-analyst", "user", "Contractor Analyst", "business-unit:endpoints", 0.35, 0.12),
]

RELATIONSHIPS = [
    ("edge:analyst-to-logistics", "asset:device-analyst-01", "asset:svc-logistics-api", "COMMUNICATED_WITH", 0.1),
    ("edge:logistics-to-comms", "asset:svc-logistics-api", "asset:svc-comms-gateway", "DEPENDS_ON", 0.2),
    ("edge:comms-to-identity", "asset:svc-comms-gateway", "asset:svc-identity-broker", "AUTHENTICATED_TO", 0.18),
    ("edge:logistics-to-audit", "asset:svc-logistics-api", "asset:database-audit-store", "DEPENDS_ON", 0.22),
    ("edge:logistics-to-pii", "asset:svc-logistics-api", "asset:database-customer-pii", "DEPENDS_ON", 0.25),
    ("edge:logistics-to-shipment-db", "asset:svc-shipment-scheduler", "asset:database-shipment-records", "DEPENDS_ON", 0.2),
    ("edge:fleet-to-logistics", "asset:svc-fleet-coordinator", "asset:svc-logistics-api", "DEPENDS_ON", 0.15),
    ("edge:route-opt-to-logistics", "asset:svc-route-optimizer", "asset:svc-logistics-api", "DEPENDS_ON", 0.12),
    ("edge:dispatch-to-logistics", "asset:device-dispatch-terminal", "asset:svc-logistics-api", "COMMUNICATED_WITH", 0.1),
    ("edge:comms-to-message-bus", "asset:svc-comms-gateway", "asset:svc-message-bus", "DEPENDS_ON", 0.15),
    ("edge:notifications-to-comms", "asset:svc-notification-service", "asset:svc-comms-gateway", "DEPENDS_ON", 0.1),
    ("edge:identity-to-sso", "asset:svc-identity-broker", "asset:svc-sso-broker", "DEPENDS_ON", 0.2),
    ("edge:identity-to-vault", "asset:svc-identity-broker", "asset:svc-service-account-vault", "ADMINISTERS", 0.25),
    ("edge:bot-to-identity", "asset:identity-svc-logistics-bot", "asset:svc-identity-broker", "AUTHENTICATED_TO", 0.3),
    ("edge:bot-to-logistics", "asset:identity-svc-logistics-bot", "asset:svc-logistics-api", "COMMUNICATED_WITH", 0.28),
    ("edge:cicd-to-k8s", "asset:svc-cicd-pipeline", "asset:svc-k8s-control-plane", "ADMINISTERS", 0.3),
    ("edge:cicd-to-registry", "asset:svc-cicd-pipeline", "asset:svc-container-registry", "DEPENDS_ON", 0.2),
    ("edge:k8s-to-logistics", "asset:svc-k8s-control-plane", "asset:svc-logistics-api", "HOSTS", 0.22),
    ("edge:secrets-to-identity", "asset:svc-secrets-manager", "asset:svc-identity-broker", "DEPENDS_ON", 0.18),
    ("edge:field-tablet-to-comms", "asset:device-field-tablet-02", "asset:svc-comms-gateway", "COMMUNICATED_WITH", 0.12),
    ("edge:vendor-vpn-to-jumphost", "asset:device-vendor-vpn-03", "asset:device-ops-jumphost", "COMMUNICATED_WITH", 0.2),
    ("edge:jumphost-to-k8s", "asset:device-ops-jumphost", "asset:svc-k8s-control-plane", "ADMINISTERS", 0.25),
    ("edge:analytics-to-pii", "asset:database-analytics-warehouse", "asset:database-customer-pii", "DEPENDS_ON", 0.15),
    ("edge:siem-to-logistics", "asset:svc-siem-forwarder", "asset:svc-logistics-api", "COMMUNICATED_WITH", 0.08),
    ("edge:edr-to-endpoints", "asset:svc-edr-console", "asset:device-analyst-01", "ADMINISTERS", 0.1),
    ("edge:inference-to-model", "asset:svc-routing-inference-gateway", "asset:ai-model-logistics-router", "DEPENDS_ON", 0.2),
    ("edge:inference-to-logistics", "asset:svc-routing-inference-gateway", "asset:svc-logistics-api", "DEPENDS_ON", 0.18),
    ("edge:feature-store-to-inference", "asset:svc-feature-store", "asset:svc-routing-inference-gateway", "DEPENDS_ON", 0.12),
    ("edge:contractor-to-jumphost", "asset:user-contractor-analyst", "asset:device-ops-jumphost", "COMMUNICATED_WITH", 0.15),
    ("edge:devops-to-cicd", "asset:user-devops-lead", "asset:svc-cicd-pipeline", "ADMINISTERS", 0.2),
]


def main() -> None:
    manifest = {
        "schemaVersion": 1,
        "metadata": {
            "scenarioId": "scenario:operation-silent-relay",
            "name": "Operation Silent Relay",
            "description": (
                "Flagship AEGIS scenario: multi-cause logistics compromise with "
                "seed-selected root causes and operator response branches."
            ),
            "version": "1.0.0",
            "requiredPlatformVersion": "0.0.0-phase10",
        },
        "zones": ZONES,
        "assets": [
            {
                "id": asset_id,
                "assetType": asset_type,
                "label": label,
                "zoneId": zone_id,
                "criticality": criticality,
                "initialRiskScore": risk,
                "initialStatus": "normal",
            }
            for asset_id, asset_type, label, zone_id, criticality, risk in ASSETS
        ],
        "relationships": [
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "relationshipType": rel_type,
                "directed": True,
                "confidence": 1.0,
                "riskContribution": risk,
            }
            for edge_id, source, target, rel_type, risk in RELATIONSHIPS
        ],
        "generators": [
            {
                "id": "gen-baseline-auth",
                "targetAssetId": "asset:svc-identity-broker",
                "plugin": {
                    "pluginId": "telemetry.auth_attempt",
                    "config": {"failureRate": 0.03, "successRate": 0.97},
                },
                "schedule": {"intervalSimSeconds": 20, "jitterSimSeconds": 2},
            },
            {
                "id": "gen-baseline-api-logistics",
                "targetAssetId": "asset:svc-logistics-api",
                "plugin": {
                    "pluginId": "telemetry.api_request",
                    "config": {"requestsPerInterval": 25, "errorRate": 0.02},
                },
                "schedule": {"intervalSimSeconds": 15, "jitterSimSeconds": 1},
            },
            {
                "id": "gen-baseline-api-comms",
                "targetAssetId": "asset:svc-comms-gateway",
                "plugin": {
                    "pluginId": "telemetry.api_request",
                    "config": {"requestsPerInterval": 18, "errorRate": 0.02},
                },
                "schedule": {"intervalSimSeconds": 18, "jitterSimSeconds": 1},
            },
            {
                "id": "gen-baseline-db-audit",
                "targetAssetId": "asset:database-audit-store",
                "plugin": {
                    "pluginId": "telemetry.database_query",
                    "config": {"queriesPerInterval": 8, "anomalyRate": 0.01},
                },
                "schedule": {"intervalSimSeconds": 25, "jitterSimSeconds": 2},
            },
            {
                "id": "gen-baseline-db-pii",
                "targetAssetId": "asset:database-customer-pii",
                "plugin": {
                    "pluginId": "telemetry.database_query",
                    "config": {"queriesPerInterval": 6, "anomalyRate": 0.01},
                },
                "schedule": {"intervalSimSeconds": 30, "jitterSimSeconds": 2},
            },
            {
                "id": "gen-baseline-network-comms",
                "targetAssetId": "asset:svc-comms-gateway",
                "plugin": {
                    "pluginId": "telemetry.network_flow",
                    "config": {"bytesPerInterval": 2048, "protocol": "tcp"},
                },
                "schedule": {"intervalSimSeconds": 12, "jitterSimSeconds": 1},
            },
            {
                "id": "gen-baseline-deploy-cicd",
                "targetAssetId": "asset:svc-cicd-pipeline",
                "plugin": {
                    "pluginId": "telemetry.deployment_event",
                    "config": {"deploymentsPerInterval": 1, "failureRate": 0.02},
                },
                "schedule": {"intervalSimSeconds": 60, "jitterSimSeconds": 5},
            },
            {
                "id": "gen-baseline-health-logistics",
                "targetAssetId": "asset:svc-logistics-api",
                "plugin": {
                    "pluginId": "telemetry.health_check",
                    "config": {"healthyProbability": 0.97},
                },
                "schedule": {"intervalSimSeconds": 20, "jitterSimSeconds": 1},
            },
            {
                "id": "gen-baseline-health-comms",
                "targetAssetId": "asset:svc-comms-gateway",
                "plugin": {
                    "pluginId": "telemetry.health_check",
                    "config": {"healthyProbability": 0.96},
                },
                "schedule": {"intervalSimSeconds": 20, "jitterSimSeconds": 1},
            },
            {
                "id": "gen-baseline-process-analyst",
                "targetAssetId": "asset:device-analyst-01",
                "plugin": {
                    "pluginId": "telemetry.process_activity",
                    "config": {"eventsPerInterval": 12, "suspiciousRate": 0.02},
                },
                "schedule": {"intervalSimSeconds": 22, "jitterSimSeconds": 2},
            },
            {
                "id": "gen-baseline-process-jumphost",
                "targetAssetId": "asset:device-ops-jumphost",
                "plugin": {
                    "pluginId": "telemetry.process_activity",
                    "config": {"eventsPerInterval": 8, "suspiciousRate": 0.02},
                },
                "schedule": {"intervalSimSeconds": 25, "jitterSimSeconds": 2},
            },
            {
                "id": "gen-baseline-ai-inference",
                "targetAssetId": "asset:svc-routing-inference-gateway",
                "plugin": {
                    "pluginId": "telemetry.ai_inference",
                    "config": {"inferencesPerInterval": 10, "anomalyRate": 0.01},
                },
                "schedule": {"intervalSimSeconds": 16, "jitterSimSeconds": 1},
            },
            {
                "id": "gen-distractor-patch-auth",
                "targetAssetId": "asset:svc-sso-broker",
                "plugin": {
                    "pluginId": "telemetry.auth_attempt",
                    "config": {"failureRate": 0.08, "successRate": 0.92},
                },
                "schedule": {"intervalSimSeconds": 45, "jitterSimSeconds": 3},
            },
            {
                "id": "gen-distractor-ci-deploy",
                "targetAssetId": "asset:svc-container-registry",
                "plugin": {
                    "pluginId": "telemetry.deployment_event",
                    "config": {"deploymentsPerInterval": 1, "failureRate": 0.01},
                },
                "schedule": {"intervalSimSeconds": 90, "jitterSimSeconds": 5},
            },
            {
                "id": "gen-distractor-analytics-batch",
                "targetAssetId": "asset:database-analytics-warehouse",
                "plugin": {
                    "pluginId": "telemetry.database_query",
                    "config": {"queriesPerInterval": 15, "anomalyRate": 0.03},
                },
                "schedule": {"intervalSimSeconds": 40, "jitterSimSeconds": 3},
            },
        ],
        "hiddenConditions": [
            {
                "id": "hidden-cause-compromised-credentials",
                "causeLabel": "Compromised service account credentials",
                "triggerRefs": ["evt-signal-credentials-auth", "evt-signal-credentials-lateral"],
                "effectRefs": ["evt-effect-credentials-status"],
                "visibility": {"mode": "hidden_until_triggered", "revealAfterSimSeconds": 600},
                "triggerThreshold": 1,
            },
            {
                "id": "hidden-cause-undocumented-maintenance",
                "causeLabel": "Approved undocumented maintenance window",
                "triggerRefs": ["evt-signal-maintenance-deploy", "evt-signal-maintenance-health"],
                "effectRefs": ["evt-effect-maintenance-status"],
                "visibility": {"mode": "hidden_until_triggered", "revealAfterSimSeconds": 720},
                "triggerThreshold": 1,
            },
            {
                "id": "hidden-cause-defective-deployment",
                "causeLabel": "Defective container deployment release",
                "triggerRefs": ["evt-signal-deployment-api", "evt-signal-deployment-health"],
                "effectRefs": ["evt-effect-deployment-status"],
                "visibility": {"mode": "hidden_until_triggered", "revealAfterSimSeconds": 540},
                "triggerThreshold": 1,
            },
            {
                "id": "hidden-cause-internal-misuse",
                "causeLabel": "Internal privileged misuse and data exfiltration",
                "triggerRefs": ["evt-signal-misuse-db", "evt-signal-misuse-network"],
                "effectRefs": ["evt-effect-misuse-status"],
                "visibility": {"mode": "hidden_until_triggered", "revealAfterSimSeconds": 660},
                "triggerThreshold": 1,
            },
        ],
        "scheduledEvents": _scheduled_events(),
        "branches": _branches(),
        "objectives": [
            {
                "id": "objective-detect-cause",
                "label": "Identify the true root cause",
                "successCriteria": "Correct hidden cause identified with supporting evidence",
                "failureCriteria": "Incorrect cause attribution or missed detection window",
            },
            {
                "id": "objective-proportionate-response",
                "label": "Execute a proportionate response",
                "successCriteria": "Response matches threat severity without excessive service impact",
                "failureCriteria": "Over-containment or failure to contain active threat",
            },
            {
                "id": "objective-preserve-evidence",
                "label": "Preserve investigation evidence",
                "successCriteria": "Key telemetry and access paths retained for replay",
                "failureCriteria": "Evidence destroyed by premature aggressive containment",
            },
        ],
        "scoring": {
            "maxScore": 100,
            "criteria": [
                {
                    "id": "criterion-detection-speed",
                    "label": "Detection speed",
                    "weight": 0.15,
                    "description": "Time to first credible alert on true cause",
                },
                {
                    "id": "criterion-evidence-coverage",
                    "label": "Evidence coverage",
                    "weight": 0.15,
                    "description": "Fraction of expected evidence chain reviewed",
                },
                {
                    "id": "criterion-hypothesis-quality",
                    "label": "Hypothesis quality",
                    "weight": 0.15,
                    "description": "Accuracy of root-cause hypothesis vs distractors",
                },
                {
                    "id": "criterion-false-positive-cost",
                    "label": "False-positive cost",
                    "weight": 0.1,
                    "description": "Penalty for containment based on distractor signals",
                },
                {
                    "id": "criterion-response-proportionality",
                    "label": "Response proportionality",
                    "weight": 0.15,
                    "description": "Alignment of response branch with threat severity",
                },
                {
                    "id": "criterion-service-impact",
                    "label": "Service impact",
                    "weight": 0.15,
                    "description": "Operational disruption from containment actions",
                },
                {
                    "id": "criterion-recurrence",
                    "label": "Recurrence handling",
                    "weight": 0.1,
                    "description": "Whether repeated signals are addressed without regression",
                },
                {
                    "id": "criterion-objectives",
                    "label": "Objectives completion",
                    "weight": 0.05,
                    "description": "Success against declared scenario objectives",
                },
            ],
            "rubric": (
                "Operation Silent Relay scoring rewards correct cause identification "
                "using overlapping signals, penalises false hypotheses supported only "
                "by distractor telemetry, and balances response speed against service impact."
            ),
        },
        "media": [
            {
                "id": "media-briefing",
                "path": "briefing.md",
                "contentType": "text/markdown",
                "description": "Operator briefing document",
            },
            {
                "id": "media-overview",
                "path": "presentation/overview.md",
                "contentType": "text/markdown",
                "description": "Narrative overview for cinematic phases",
            },
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        yaml.dump(manifest, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT}")


def _branches() -> list[dict]:
    return [
        {
            "id": "branch-cause-credentials",
            "label": "Compromised credentials path",
            "weight": 0.25,
            "branchGroup": "root-cause",
            "triggerCondition": "elevated_auth_failures_and_lateral_movement",
            "outcomes": [
                {
                    "targetRef": "hidden-cause-compromised-credentials",
                    "description": "Service account compromise drives logistics API access",
                }
            ],
        },
        {
            "id": "branch-cause-maintenance",
            "label": "Undocumented maintenance path",
            "weight": 0.25,
            "branchGroup": "root-cause",
            "triggerCondition": "off_window_deployment_and_health_flap",
            "outcomes": [
                {
                    "targetRef": "hidden-cause-undocumented-maintenance",
                    "description": "Approved maintenance executed outside declared window",
                }
            ],
        },
        {
            "id": "branch-cause-deployment",
            "label": "Defective deployment path",
            "weight": 0.25,
            "branchGroup": "root-cause",
            "triggerCondition": "api_error_spike_and_failed_health_checks",
            "outcomes": [
                {
                    "targetRef": "hidden-cause-defective-deployment",
                    "description": "Bad container release degrades logistics API",
                }
            ],
        },
        {
            "id": "branch-cause-misuse",
            "label": "Internal misuse path",
            "weight": 0.25,
            "branchGroup": "root-cause",
            "triggerCondition": "privileged_db_anomaly_and_exfil_network",
            "outcomes": [
                {
                    "targetRef": "hidden-cause-internal-misuse",
                    "description": "Privileged user exfiltrates customer data",
                }
            ],
        },
        {
            "id": "branch-response-contain",
            "label": "Aggressive containment",
            "weight": 0.34,
            "branchGroup": "response-path",
            "triggerCondition": "operator_isolates_suspected_assets",
            "outcomes": [
                {
                    "targetRef": "evt-consequence-contain",
                    "description": "Fast isolation with higher service impact",
                }
            ],
        },
        {
            "id": "branch-response-investigate",
            "label": "Methodical investigation",
            "weight": 0.33,
            "branchGroup": "response-path",
            "triggerCondition": "operator_preserves_evidence_first",
            "outcomes": [
                {
                    "targetRef": "evt-consequence-investigate",
                    "description": "Slower containment with richer evidence",
                }
            ],
        },
        {
            "id": "branch-response-remediate",
            "label": "Root-cause remediation",
            "weight": 0.33,
            "branchGroup": "response-path",
            "triggerCondition": "operator_patches_underlying_fault",
            "outcomes": [
                {
                    "targetRef": "evt-consequence-remediate",
                    "description": "Fix deployment or credential root with moderate risk",
                }
            ],
        },
    ]


def _scheduled_events() -> list[dict]:
    events: list[dict] = [
        {
            "id": "evt-select-root-cause",
            "simTime": "2026-01-01T00:00:00.000Z",
            "priority": 0,
            "tieBreaker": 0,
            "action": {
                "pluginId": "branch.seed_selector",
                "config": {"branchGroup": "root-cause"},
            },
        },
        {
            "id": "evt-select-response-path",
            "simTime": "2026-01-01T00:00:00.001Z",
            "priority": 0,
            "tieBreaker": 1,
            "action": {
                "pluginId": "branch.seed_selector",
                "config": {"branchGroup": "response-path"},
            },
        },
    ]
    cause_signals = [
        (
            "credentials",
            "branch-cause-credentials",
            [
                (
                    "evt-signal-credentials-auth",
                    "2026-01-01T00:05:00.000Z",
                    "asset:svc-identity-broker",
                    "telemetry.auth_attempt",
                    {"failureRate": 0.65, "successRate": 0.35},
                ),
                (
                    "evt-signal-credentials-lateral",
                    "2026-01-01T00:08:00.000Z",
                    "asset:svc-logistics-api",
                    "telemetry.auth_attempt",
                    {"failureRate": 0.1, "successRate": 0.9},
                ),
            ],
            ("evt-effect-credentials-status", "asset:identity-svc-logistics-bot", "compromised"),
        ),
        (
            "maintenance",
            "branch-cause-maintenance",
            [
                (
                    "evt-signal-maintenance-deploy",
                    "2026-01-01T00:06:00.000Z",
                    "asset:svc-cicd-pipeline",
                    "telemetry.deployment_event",
                    {"deploymentsPerInterval": 2, "failureRate": 0.4},
                ),
                (
                    "evt-signal-maintenance-health",
                    "2026-01-01T00:09:00.000Z",
                    "asset:svc-comms-gateway",
                    "telemetry.health_check",
                    {"healthyProbability": 0.35},
                ),
            ],
            ("evt-effect-maintenance-status", "asset:svc-comms-gateway", "suspicious"),
        ),
        (
            "deployment",
            "branch-cause-deployment",
            [
                (
                    "evt-signal-deployment-api",
                    "2026-01-01T00:07:00.000Z",
                    "asset:svc-logistics-api",
                    "telemetry.api_request",
                    {"requestsPerInterval": 40, "errorRate": 0.55},
                ),
                (
                    "evt-signal-deployment-health",
                    "2026-01-01T00:10:00.000Z",
                    "asset:svc-logistics-api",
                    "telemetry.health_check",
                    {"healthyProbability": 0.2},
                ),
            ],
            ("evt-effect-deployment-status", "asset:svc-logistics-api", "suspicious"),
        ),
        (
            "misuse",
            "branch-cause-misuse",
            [
                (
                    "evt-signal-misuse-db",
                    "2026-01-01T00:06:30.000Z",
                    "asset:database-customer-pii",
                    "telemetry.database_query",
                    {"queriesPerInterval": 50, "anomalyRate": 0.85},
                ),
                (
                    "evt-signal-misuse-network",
                    "2026-01-01T00:09:30.000Z",
                    "asset:device-ops-jumphost",
                    "telemetry.network_flow",
                    {"bytesPerInterval": 65536, "protocol": "tcp"},
                ),
            ],
            ("evt-effect-misuse-status", "asset:database-customer-pii", "under_investigation"),
        ),
    ]
    for _name, branch_id, signals, effect in cause_signals:
        effect_id, asset_id, status = effect
        for sig_id, sim_time, target_asset, plugin_id, config in signals:
            events.append(
                {
                    "id": sig_id,
                    "simTime": sim_time,
                    "priority": 2,
                    "tieBreaker": 0,
                    "targetAssetId": target_asset,
                    "branchGate": {"branchGroup": "root-cause", "branchId": branch_id},
                    "action": {
                        "pluginId": plugin_id,
                        "config": config,
                    },
                }
            )
        events.append(
            {
                "id": effect_id,
                "simTime": "2026-01-01T00:15:00.000Z",
                "priority": 3,
                "tieBreaker": 0,
                "targetAssetId": asset_id,
                "branchGate": {"branchGroup": "root-cause", "branchId": branch_id},
                "action": {
                    "pluginId": "effect.set_asset_status",
                    "config": {"status": status},
                },
            }
        )
    response_consequences = [
        (
            "evt-consequence-contain",
            "branch-response-contain",
            "asset:svc-logistics-api",
            "contained",
            "edge:logistics-to-comms",
            -0.4,
        ),
        (
            "evt-consequence-investigate",
            "branch-response-investigate",
            "asset:svc-logistics-api",
            "under_investigation",
            "edge:bot-to-logistics",
            -0.15,
        ),
        (
            "evt-consequence-remediate",
            "branch-response-remediate",
            "asset:svc-cicd-pipeline",
            "under_investigation",
            "edge:cicd-to-k8s",
            0.1,
        ),
    ]
    for event_id, branch_id, asset_id, status, edge_id, delta in response_consequences:
        events.append(
            {
                "id": event_id,
                "simTime": "2026-01-01T00:20:00.000Z",
                "priority": 4,
                "tieBreaker": 0,
                "targetAssetId": asset_id,
                "branchGate": {"branchGroup": "response-path", "branchId": branch_id},
                "action": {
                    "pluginId": "effect.set_asset_status",
                    "config": {"status": status},
                },
            }
        )
        events.append(
            {
                "id": f"{event_id}-edge",
                "simTime": "2026-01-01T00:21:00.000Z",
                "priority": 4,
                "tieBreaker": 1,
                "branchGate": {"branchGroup": "response-path", "branchId": branch_id},
                "action": {
                    "pluginId": "effect.adjust_relationship_confidence",
                    "config": {"edgeId": edge_id, "delta": delta},
                },
            }
        )
    return events


if __name__ == "__main__":
    main()

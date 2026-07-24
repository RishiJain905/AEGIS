"""MITRE ATT&CK kill-chain shared vocabulary.

The attacker kill-chain engine (in the simulation-domain package) and the scenario
authoring layer (scenario-sdk) both need a single, stable set of ATT&CK *tactic*
identifiers plus the domain event types the engine emits as an attacker campaign
advances. Keeping them here — in the shared contracts package — means the scenario
manifest, the simulation runtime, and (later) the graph projection and scoring all
speak one vocabulary instead of independently redefining string constants.

This module is additive and Python-only for now: campaign *authoring* structures
live in the scenario-sdk manifest schema and campaign *runtime* progression is held
in the simulation world state. No cross-language (TS) mirror is required until a
boundary actually serializes technique state to the browser (Phase 3+).
"""

from __future__ import annotations

from enum import StrEnum


class AttackTactic(StrEnum):
    """MITRE ATT&CK tactics an authored kill-chain technique may realize.

    Values are the canonical ATT&CK tactic shortnames so authored campaigns and any
    downstream ATT&CK mapping line up without translation.
    """

    INITIAL_ACCESS = "initial_access"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DEFENSE_EVASION = "defense_evasion"
    CREDENTIAL_ACCESS = "credential_access"
    DISCOVERY = "discovery"
    LATERAL_MOVEMENT = "lateral_movement"
    COLLECTION = "collection"
    COMMAND_AND_CONTROL = "command_and_control"
    EXFILTRATION = "exfiltration"
    IMPACT = "impact"


# Domain event types the kill-chain engine appends to the authoritative event stream.
# These are truth (fog-of-war disclosure is applied only when projecting to operators).
KILLCHAIN_CAMPAIGN_ACTIVATED = "sim.killchain.campaign_activated"
KILLCHAIN_TECHNIQUE_EXECUTED = "sim.killchain.technique_executed"
KILLCHAIN_REACTION_FIRED = "sim.killchain.reaction_fired"
KILLCHAIN_EXFILTRATION_COMPLETED = "sim.killchain.exfiltration_completed"
KILLCHAIN_CAMPAIGN_STALLED = "sim.killchain.campaign_stalled"


class CampaignStatus(StrEnum):
    """Lifecycle of an in-world attacker campaign.

    ``ACTIVE`` advances on the sim clock; ``STALLED`` has been cut off with no
    established fallback capability remaining (a defensive win in the making);
    ``SUCCEEDED`` reached exfiltration. Phase 2 turns these into run win/lose
    resolution; Phase 1 only needs the engine to reach and record them.
    """

    ACTIVE = "active"
    STALLED = "stalled"
    SUCCEEDED = "succeeded"

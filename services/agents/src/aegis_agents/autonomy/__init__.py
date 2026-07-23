"""Phase 7 autonomous triage loop.

Event-driven (NOT per-tick LLM churn): when the live detection pipeline persists a NEW
alert, a bounded WATCHTOWER auto-task is enqueued on the run's dedicated autonomy session.
Rules-of-engagement gate how proactive the agent may be (encoded as prompt-level
instructions); budgets cap local-model load. Nothing here executes state changes — auto
tasks still produce proposals that pass policy + human approval.
"""

from aegis_agents.autonomy.service import AutonomyBudget, AutonomyTriageService

__all__ = ["AutonomyBudget", "AutonomyTriageService"]

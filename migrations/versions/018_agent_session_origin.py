# ruff: noqa: E501

"""Backfill ``origin`` on agent sessions (operator thread vs autonomy triage).

``AgentSessionV1`` gained an ``origin`` discriminator so the copilot can show only the
threads a human started; the autonomy worker's background triage sessions (WATCHTOWER
sweeps, bias-guard checks) were otherwise rendered as operator conversations, complete
with permanent "Working…" turns nobody had asked for.

Like ``role`` and ``state``, ``origin`` lives in the JSONB payload rather than a flat
column — no schema change, only a data backfill. New sessions get it at creation.

Existing rows carry no direct record of who opened them, but their tasks do: the
autonomy service stamps every task it enqueues with ``initiator = 'autonomy'``. A
session whose tasks are all autonomy-initiated is a triage thread; anything else
(operator-initiated tasks, or no tasks at all) is an operator thread, which is also
the model default, so a misclassification here can only ever leave a session visible
rather than hide one.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "018_agent_session_origin"
down_revision: str | None = "017_standing_directives"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE agent_sessions AS s "
            "SET payload = jsonb_set(payload, '{origin}', to_jsonb(cast('autonomy' as text))) "
            "WHERE EXISTS ("
            "    SELECT 1 FROM agent_tasks AS t"
            "     WHERE t.session_id = s.id AND t.payload->>'initiator' = 'autonomy'"
            ") AND NOT EXISTS ("
            "    SELECT 1 FROM agent_tasks AS t"
            "     WHERE t.session_id = s.id"
            "       AND coalesce(t.payload->>'initiator', 'operator') <> 'autonomy'"
            ")"
        )
    )
    op.execute(
        sa.text(
            "UPDATE agent_sessions "
            "SET payload = jsonb_set(payload, '{origin}', to_jsonb(cast('operator' as text))) "
            "WHERE NOT (payload ? 'origin')"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("UPDATE agent_sessions SET payload = payload - 'origin'"))

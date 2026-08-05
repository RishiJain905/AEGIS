"""Evidence citation grounding: the valid-id catalogue, and what violates it.

Grounding is the one contract the model cannot be trusted to keep on its own. A
local model asked for ``evidenceCitations`` will happily invent ``ALERT-001``,
``EV001`` or ``INC-TITLE-SSO-001`` — plausible-looking strings that are not AEGIS
identifiers at all. Two things in this module answer that:

* :func:`build_evidence_catalogue` produces the compact, bounded list of ids the
  model is allowed to cite. Injecting it is *prevention*: before it existed, an
  incident-scoped turn was asked for citations while being shown no evidence ids
  whatsoever, so inventing one was the only move its schema left it.
* :func:`invalid_citation_ids` names exactly which ids a given answer got wrong,
  which is what the executor's bounded repair round-trip shows the model.

:func:`validate_citations` remains the strict gate on the audit path. Repair
happens strictly before it; nothing here relaxes it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_contracts.agent_runtime import EvidenceCitationV1
from aegis_contracts.entities import EvidenceV1

#: Cardinality and per-string bounds for the injected catalogue. The catalogue is
#: a *list of ids*, so it stays far cheaper than the run-state snapshot even at
#: the cap; the summary is only there so the model can pick the right id.
MAX_CATALOGUE_EVIDENCE = 60
MAX_CATALOGUE_SUMMARY_CHARS = 140


def build_evidence_catalogue(evidence: Sequence[EvidenceV1]) -> dict[str, Any]:
    """The authoritative set of evidence ids this task may cite.

    Bounded to the most recent :data:`MAX_CATALOGUE_EVIDENCE` items (repository
    listings are oldest-first, so the tail is the newest), and it reports the true
    total so a model can tell "there is no evidence" from "I was shown a window
    onto more". Truncation is safe in the direction that matters: the validator
    accepts every visible id, so a shown id is always valid — the catalogue can
    only ever under-offer, never mislead.
    """
    shown = list(evidence[-MAX_CATALOGUE_EVIDENCE:])
    return {
        "total": len(evidence),
        "shown": len(shown),
        "truncated": len(shown) < len(evidence),
        "items": [
            {
                "evidenceId": item.id,
                "summary": (item.summary or "")[:MAX_CATALOGUE_SUMMARY_CHARS],
            }
            for item in shown
        ],
    }


def catalogue_ids(catalogue: dict[str, Any]) -> list[str]:
    """The ids in a catalogue, for the repair prompt's "valid ids" list."""
    items = catalogue.get("items", [])
    if not isinstance(items, list):
        return []
    return [
        str(item["evidenceId"])
        for item in items
        if isinstance(item, dict) and isinstance(item.get("evidenceId"), str)
    ]


def invalid_citation_ids(
    structured: dict[str, Any] | None,
    *,
    visible_evidence_ids: set[str],
) -> list[str]:
    """The cited ids this run does not recognise, in the order the model wrote them.

    Returns an empty list both when the answer is properly grounded AND when its
    ``evidenceCitations`` is malformed in shape rather than in content (not a
    list, or entries that are not citation objects). That is deliberate: a shape
    fault is a *schema* failure, which the provider's own structured-output repair
    already owns, and re-prompting it here with a grounding complaint would send
    the model chasing the wrong problem.

    Duplicates are collapsed so a model that cited the same bad id five times gets
    one complaint about it rather than five.
    """
    if not isinstance(structured, dict):
        return []
    raw = structured.get("evidenceCitations")
    if not isinstance(raw, list):
        return []
    offending: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            return []
        evidence_id = item.get("evidenceId")
        if not isinstance(evidence_id, str) or not evidence_id:
            return []
        if evidence_id in visible_evidence_ids or evidence_id in seen:
            continue
        seen.add(evidence_id)
        offending.append(evidence_id)
    return offending


def validate_citations(
    citations: list[EvidenceCitationV1],
    *,
    visible_evidence_ids: set[str],
    trace_id: str | None = None,
) -> None:
    for citation in citations:
        if citation.evidence_id not in visible_evidence_ids:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.EVIDENCE_NOT_VISIBLE,
                message=f"Evidence citation not visible to session: {citation.evidence_id}",
                details={"evidenceId": citation.evidence_id},
                trace_id=trace_id,
            )

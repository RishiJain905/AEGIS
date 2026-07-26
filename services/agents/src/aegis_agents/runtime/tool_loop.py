"""Bounded multi-turn tool loop: classification, dedupe, and bounded results.

The runtime used to be single-shot: the model answered once, and whatever tools
it asked for ran *after* the reply, so their output never reached the model. Any
question the injected context did not already cover was unanswerable from live
data. The loop closes that gap — generate, run the read-only tools the model
asked for, hand the results back, generate again — under hard bounds.

This module holds the pure, side-effect-free half of that loop (what may run,
what has already run, and how results are bounded before they re-enter the
prompt). Orchestration — model calls, transactions, event appends — stays in
:mod:`aegis_agents.runtime.executor`, which owns the three-phase discipline.

Two bounds matter most:

* **Only READ-class tools ever run inside the loop.** Everything else is
  *deferred*: it is handed back to the persist phase, where analysis writes and
  action proposals go through the existing policy/approval pipeline. The loop is
  structurally unable to execute a state change, because the only thing it can
  hand to the tool executor is a request whose registry ``tool_class`` is READ.
* **Results are size-bounded before they re-enter the conversation.** A single
  ``search_events`` result can be tens of kilobytes; a 12B-class local model's
  context cannot absorb that, so each result is clipped and the round is capped
  on cardinality.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from aegis_agents.tools.registry import ToolRegistry
from aegis_contracts.agent_runtime import AgentToolClass, ToolDefinitionV1

# How many generate -> run tools -> generate rounds a single task may take. Each
# round costs one extra model call, so this is the main cost/latency lever.
DEFAULT_TOOL_LOOP_MAX_ITERATIONS = 3

# Per-round cardinality bound. A model that asks for eight tools at once gets the
# first few; the rest can be re-requested next round if it still wants them.
MAX_TOOL_REQUESTS_PER_ITERATION = 4

# Per-result character ceiling for the serialized tool output fed back to the
# model. Deliberately small: several results share one context window.
MAX_TOOL_RESULT_CHARS = 2_000

# Fallback ceiling applied when a whole round still serializes too large after
# per-result clipping.
MIN_TOOL_RESULT_CHARS = 400


@dataclass(frozen=True)
class ToolRequest:
    """One tool request as the model asked for it, with a stable identity."""

    name: str
    arguments: dict[str, Any]

    @property
    def key(self) -> str:
        """Identity for dedupe: the same tool with the same arguments twice.

        A model that re-asks for a query it already got back has nothing new to
        learn from running it again, so the loop treats a repeat as a signal to
        stop rather than as work.
        """
        try:
            canonical = json.dumps(self.arguments, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError):
            canonical = repr(sorted(self.arguments.items()))
        return f"{self.name}:{canonical}"

    def as_payload(self) -> dict[str, Any]:
        """The shape the persist phase expects for a deferred request."""
        return {"name": self.name, "arguments": dict(self.arguments)}


def parse_tool_requests(structured: Mapping[str, Any] | None) -> list[ToolRequest]:
    """Read ``toolRequests`` out of a structured model response, defensively.

    A local model under a strict schema still emits the occasional malformed
    entry. A bad entry is dropped rather than raising: the loop must never turn a
    usable answer into a failed task.
    """
    if not structured:
        return []
    raw = structured.get("toolRequests")
    if not isinstance(raw, list):
        return []
    requests: list[ToolRequest] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name:
            continue
        arguments = item.get("arguments")
        parsed = dict(arguments) if isinstance(arguments, Mapping) else {}
        requests.append(ToolRequest(name=name, arguments=parsed))
    return requests


def classify_tool_requests(
    requests: Iterable[ToolRequest],
    *,
    registry: ToolRegistry,
) -> tuple[list[ToolRequest], list[ToolRequest]]:
    """Split requests into ``(runnable_in_loop, deferred)``.

    Runnable means the registry classifies the tool as :attr:`AgentToolClass.READ`
    — the platform's own read-only classification, not a name list that could
    drift away from it. Everything else (analysis writes, action proposals,
    execution-class adapters, unknown names) is deferred to the persist phase,
    where proposals reach the policy/approval gate exactly as they always have.
    """
    runnable: list[ToolRequest] = []
    deferred: list[ToolRequest] = []
    for request in requests:
        definition = registry.get(request.name)
        if definition is not None and definition.tool_class == AgentToolClass.READ:
            runnable.append(request)
        else:
            deferred.append(request)
    return runnable, deferred


def _clip(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    return value[:limit], True


def _dumps(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return repr(value)


def _clip_tool_output(output: Mapping[str, Any], limit: int) -> tuple[str, bool]:
    """Fit a tool result under ``limit`` characters, keeping whole records.

    Naively slicing the serialized JSON hands the model a string that stops
    mid-record — a half-written event id reads as a real one. Tool outputs are
    consistently ``{"events": [...], "count": n}``-shaped, so shrink the longest
    list instead: the model then sees fewer complete records plus the true total
    the tool reported, which is exactly what it needs to say "there are more".
    Raw clipping stays as the last resort for a shape with no list to shrink.
    """
    serialized = _dumps(output)
    if len(serialized) <= limit:
        return serialized, False

    trimmed = dict(output)
    list_keys = sorted(
        (key for key, value in trimmed.items() if isinstance(value, list) and value),
        key=lambda key: -len(trimmed[key]),
    )
    for key in list_keys:
        items = list(trimmed[key])
        while items and len(_dumps({**trimmed, key: items})) > limit:
            items = items[: len(items) // 2]
        trimmed[key] = items
        if len(_dumps(trimmed)) <= limit:
            return _dumps(trimmed), True
    return serialized[:limit], True


def summarize_tool_result(
    *,
    request: ToolRequest,
    status: str,
    output: Mapping[str, Any] | None = None,
    error_message: str | None = None,
    max_chars: int = MAX_TOOL_RESULT_CHARS,
) -> dict[str, Any]:
    """Bound one tool result to a size a small local model can absorb."""
    summary: dict[str, Any] = {
        "tool": request.name,
        "arguments": request.arguments,
        "status": status,
    }
    if output is not None:
        clipped, truncated = _clip_tool_output(output, max_chars)
        summary["output"] = clipped
        if truncated:
            summary["outputTruncated"] = True
    if error_message:
        summary["error"] = _clip(error_message, 500)[0]
    return summary


def summarize_deferred_request(request: ToolRequest) -> dict[str, Any]:
    """Tell the model a state-changing request was recorded, not executed.

    Without this the model would see its request silently vanish and re-ask for
    it every round. The note is also the honest description of what happens: the
    request is carried to the persist phase, where it becomes a proposal for a
    human to approve.
    """
    return {
        "tool": request.name,
        "arguments": request.arguments,
        "status": "deferred",
        "note": (
            "Not executed during investigation. Only read-only tools run here; this "
            "request is recorded and, if it is a valid state-changing action, routed "
            "to the human approval gate as a proposal. Do not re-request it — "
            "conclude with what you have."
        ),
    }


def bounded_results_payload(
    results: Sequence[Mapping[str, Any]],
    *,
    max_bytes: int,
) -> list[dict[str, Any]]:
    """Re-clip a whole round if it still serializes past ``max_bytes``.

    Per-result clipping already keeps a normal round well under the ceiling; this
    is the guard for the pathological case (many tools, each at the per-result
    cap) so an oversized round degrades to shorter outputs instead of raising and
    killing the turn.
    """
    payload = [dict(item) for item in results]
    if _payload_bytes(payload) <= max_bytes:
        return payload
    for item in payload:
        output = item.get("output")
        if isinstance(output, str) and len(output) > MIN_TOOL_RESULT_CHARS:
            item["output"] = output[:MIN_TOOL_RESULT_CHARS]
            item["outputTruncated"] = True
    if _payload_bytes(payload) <= max_bytes:
        return payload
    return [
        {key: value for key, value in item.items() if key != "output"} | {"outputOmitted": True}
        for item in payload
    ]


def _payload_bytes(payload: list[dict[str, Any]]) -> int:
    return len(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def describe_available_tools(
    definitions: Sequence[ToolDefinitionV1],
    *,
    allowed_tools: Sequence[str],
    executable_tools: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Catalogue the tools a role may actually call, for the prompt.

    Nothing in the runtime ever told the model which tools exist — the provider
    adapters ignore the request's ``tools`` field, and the role system prompts
    name none — so a model could only guess tool names from memory. A loop the
    model cannot address is useless, hence this block.

    Three filters, all narrowing: the caller passes the registry's model-visible
    tools *for this role* (so a tool the role may not call is already gone), this
    function intersects with the agent definition's allowlist, and
    ``executable_tools`` drops any tool with no registered handler. The last one
    matters because advertising a tool that is always rejected spends the model's
    whole investigation budget on a call that cannot work — three TRACE graph
    tools are in that state today (``list_relationships``, ``get_graph_paths``,
    ``get_incident_timeline``). Never widens anything: authorization is still
    enforced server-side on every invocation.
    """
    allowed = set(allowed_tools)
    executable = None if executable_tools is None else set(executable_tools)
    catalogue: list[dict[str, Any]] = []
    for definition in definitions:
        if definition.name not in allowed:
            continue
        if executable is not None and definition.name not in executable:
            continue
        catalogue.append(
            {
                "name": definition.name,
                "description": definition.description,
                "arguments": definition.input_schema,
                "readOnly": definition.tool_class == AgentToolClass.READ,
            }
        )
    return catalogue

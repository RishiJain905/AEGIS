"""Posture-derived risk: what an asset's own security state is worth, before evidence.

The risk engine in :mod:`aegis_graph_risk.propagate` measures *evidence-derived* risk —
detection signals propagated across the graph. That is only half the number an operator
reads off a node. The other half is the asset's own state: an asset the attacker has
compromised is high-risk whether or not a detector happened to fire on it, and an asset
we have isolated is lower-risk than it was at its peak but higher than one that was never
touched.

Before this module existed, ``GraphNodeV1.risk_score`` carried the scenario's authored
``initial_risk_score`` for the entire life of a run and nothing ever wrote to it again.
Every asset in Operation Silent Relay therefore sat between 0.00 and 0.20 from the first
tick to the last, and a compromised database read *lower* than an untouched VPN client.
The score differentiated nothing because it was seed data, not a measurement.

The curve here is a pure, total function of ``(status, criticality)`` plus an optional
authored floor. It is deterministic by construction — no clock, no randomness, no
accumulated state — so the same world state always projects the same risk, which is what
lets it be recomputed from scratch on every tick and during replay without diverging.

Shape
-----
Each operator-facing :class:`~aegis_contracts.graph.NodeStatus` owns a **band**: a floor
plus the headroom criticality can add on top of it.

    risk = max(floor[status] + headroom[status] * criticality, authored_floor)

Bands are ordered so posture dominates and criticality ranks within a posture:

``normal`` 0.00–0.25
    At-rest exposure. Deliberately spans the range the authored baselines already used,
    so a quiet run looks the way it always did — the change is that this is now the
    *bottom* of the scale rather than the whole of it.

``under_investigation`` 0.30–0.50
    Something drew attention. Narrow headroom: we are looking, we have not found.

``contained`` 0.45–0.70
    We acted. Risk is reduced *from its compromised peak*, never to zero — a contained
    host was still compromised, and the residual is what the after-action is about. The
    floor sits below ``suspicious`` because acting resolves uncertainty, but the headroom
    is the widest of any non-baseline band, so a contained crown-jewel still outranks a
    low-value asset that is merely suspicious.

``suspicious`` 0.55–0.75
    Active, unresolved. Higher floor than ``contained`` for exactly that reason.

``compromised`` 0.80–1.00
    Owned. The band is disjoint from every other floor, so *any* compromised asset
    outranks *every* asset that is not compromised, regardless of criticality.

The authored ``initial_risk_score`` enters only as a lower bound. It never reduces a
node's risk, so scenario authoring keeps its ability to say "this vendor laptop is
already exposed at rest" without being able to hide a compromise.

Containment is read off the composed status rather than modelled separately: by the time
a node reaches this function, :func:`~aegis_contracts.killchain.project_effective_status`
has already folded applied controls into ``contained``, which is precisely the band drop
this curve wants to express.
"""

from __future__ import annotations

from aegis_contracts.graph import NodeStatus

#: Lower bound of each posture's risk band.
POSTURE_RISK_FLOOR: dict[str, float] = {
    NodeStatus.NORMAL.value: 0.00,
    NodeStatus.UNDER_INVESTIGATION.value: 0.30,
    NodeStatus.CONTAINED.value: 0.45,
    NodeStatus.SUSPICIOUS.value: 0.55,
    NodeStatus.COMPROMISED.value: 0.80,
}

#: How much of the band above the floor an asset's criticality can claim.
POSTURE_RISK_HEADROOM: dict[str, float] = {
    NodeStatus.NORMAL.value: 0.25,
    NodeStatus.UNDER_INVESTIGATION.value: 0.20,
    NodeStatus.CONTAINED.value: 0.25,
    NodeStatus.SUSPICIOUS.value: 0.20,
    NodeStatus.COMPROMISED.value: 0.20,
}

#: Band applied to a status outside the known vocabulary. Matches
#: :func:`~aegis_contracts.killchain.project_node_status`, which projects anything
#: unrecognized to ``under_investigation``: something moved this asset off baseline and
#: we do not know what.
_UNKNOWN_STATUS_BAND = (
    POSTURE_RISK_FLOOR[NodeStatus.UNDER_INVESTIGATION.value],
    POSTURE_RISK_HEADROOM[NodeStatus.UNDER_INVESTIGATION.value],
)


def posture_risk(status: str, criticality: float, *, authored_floor: float = 0.0) -> float:
    """Risk an asset carries from its own posture and criticality alone.

    ``status`` is the operator-facing composed status already on the node (posture with
    applied controls folded in). ``authored_floor`` is the scenario's
    ``initial_risk_score`` where the caller has it; it can only raise the result.

    Total by construction: an unrecognized status is banded as ``under_investigation``
    rather than raising, because this runs inside the graph projection on every tick and
    a raise here would strand the run.
    """
    if status in POSTURE_RISK_FLOOR:
        floor = POSTURE_RISK_FLOOR[status]
        headroom = POSTURE_RISK_HEADROOM[status]
    else:
        floor, headroom = _UNKNOWN_STATUS_BAND
    banded = floor + headroom * _clamp(criticality)
    return _clamp(max(banded, authored_floor))


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))

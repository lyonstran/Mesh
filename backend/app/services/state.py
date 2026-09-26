"""Request state machine for the MVP (PLAN.md §0.1; subset of §9.7)."""

from typing import Literal

from app.errors import APIError
from app.models import RequestStatus as S

# "requester" = the request's owner; "assigned_helper" = the helper who claimed it;
# "helper" = any volunteer (only used for claiming).
Actor = Literal["requester", "assigned_helper", "helper"]

TRANSITIONS: dict[tuple[S, S], frozenset[str]] = {
    (S.OPEN, S.CLAIMED): frozenset({"helper"}),
    (S.OPEN, S.CANCELLED): frozenset({"requester"}),
    (S.CLAIMED, S.RESOLVED): frozenset({"requester", "assigned_helper"}),
    (S.CLAIMED, S.OPEN): frozenset({"assigned_helper"}),
    (S.CLAIMED, S.CANCELLED): frozenset({"requester"}),
}


def check_transition(current: S, target: S, actor: Actor) -> None:
    """Raise 409 INVALID_TRANSITION unless `actor` may move a request from `current` to `target`."""
    allowed = TRANSITIONS.get((current, target))
    if not allowed or actor not in allowed:
        raise APIError(409, "INVALID_TRANSITION", f"Can't change a {current} request to {target}")

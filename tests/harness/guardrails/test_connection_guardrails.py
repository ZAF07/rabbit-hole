"""Connection guardrail evaluator — set-level, binary FAIL-if checks."""

from harness.domain.artifacts import WiredConnection
from harness.guardrails.connection import evaluate_connections

GOOD_RATIONALE = (
    "GPS satellites drift 38 microseconds a day exactly as relativity predicts, "
    "so the map on a phone depends on Einstein being right."
)
GOOD_HOOK = "Why does your phone's map depend on Einstein being right?"


def edge(
    from_id: str = "gps",
    to_id: str = "relativity",
    hook: str = GOOD_HOOK,
    rationale: str = GOOD_RATIONALE,
) -> WiredConnection:
    return WiredConnection(from_piece_id=from_id, to_piece_id=to_id, hook=hook, rationale=rationale)


def codes(*connections: WiredConnection, banned: tuple[str, ...] = ()) -> set[str]:
    return {v.code for v in evaluate_connections(connections, banned)}


def test_shared_topic_adjacency_fails_a1():
    assert "A1" in codes(edge(rationale="Both are about economics."))


def test_missing_rationale_fails_a1():
    assert "A1" in codes(edge(rationale="   "))


def test_specific_relationship_passes_a1():
    assert "A1" not in codes(edge())


def test_hook_identical_from_any_origin_fails_b3():
    same_hook = "What the container did to the price of everything."
    first = edge(from_id="tshirt", to_id="container", hook=same_hook)
    second = edge(from_id="suez", to_id="container", hook=same_hook)
    assert "B3" in codes(first, second)


def test_distinct_per_origin_hooks_pass_b3():
    first = edge(from_id="tshirt", to_id="container", hook="How a $3 shirt crosses three oceans.")
    second = edge(from_id="suez", to_id="container", hook="The box that jammed a canal.")
    assert "B3" not in codes(first, second)


def test_generic_lure_hook_fails_b1():
    assert "B1" in codes(edge(hook="Learn about GPS."))


def test_empty_hook_fails_b1():
    assert "B1" in codes(edge(hook=""))


def test_curiosity_gap_hook_passes_b1():
    assert "B1" not in codes(edge())


def test_banned_filler_in_hook_fails_b5():
    assert "B5" in codes(
        edge(hook="The game-changer hiding in your pocket?"), banned=("game-changer",)
    )


def test_evaluator_is_deterministic():
    edges = (edge(rationale="Both cover history."), edge(from_id="b", hook="Learn more."))
    banned: tuple[str, ...] = ()
    assert evaluate_connections(edges, banned) == evaluate_connections(edges, banned)

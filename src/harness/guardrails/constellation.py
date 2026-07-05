"""Constellation-level checks (``harness/guardrails/constellation.md``).

Tier 1 — the hard invariants I1–I8, the run's outcome contract — is fully
mechanical and returned as **binary** pass/fail per invariant, never a score.
Tier 2 — journey coherence J1–J5 — is Reviewer-judged; this module only
defines its structure (:data:`TIER2_CODES`, :class:`Tier2Judgement`).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from harness.domain.artifacts import ConstellationArtifact, PieceArtifact
from harness.domain.grounding import ClaimStatus, GroundingLedger
from harness.guardrails.connection import evaluate_connections
from harness.guardrails.piece import evaluate_piece
from harness.guardrails.violations import Violation

TIER1_CODES: tuple[str, ...] = ("I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8")

TIER2_CODES: Mapping[str, str] = {
    "J1": "not all-obvious — real cross-Topic surprise density",
    "J2": "no near-duplicate Pieces",
    "J3": "entry-worthy nodes exist — a Piece works cold as a Daily Feature",
    "J4": "pacing spread — the constellation has range",
    "J5": "coherent theme — the Brief's through-line is visible",
}


@dataclass(frozen=True)
class Tier2Judgement:
    """One Reviewer-judged coherence verdict.

    Attributes:
        code: The J-check judged (``J1``–``J5``).
        passed: The verdict.
        note: The Reviewer's reason, kept for the QA report.
    """

    code: str
    passed: bool
    note: str = ""


@dataclass(frozen=True)
class Tier1Report:
    """The binary outcome-contract verdict for one constellation.

    Attributes:
        results: Invariant code → pass/fail, one entry per I1–I8.
        violations: The specific failures behind every False entry.
    """

    results: Mapping[str, bool]
    violations: tuple[Violation, ...]

    @property
    def passed(self) -> bool:
        """Whether every hard invariant holds.

        Returns:
            True only if all of I1–I8 pass.
        """
        return all(self.results.values())

    def failed_codes(self) -> tuple[str, ...]:
        """Return the invariants that failed.

        Returns:
            The failing codes, in I1–I8 order.
        """
        return tuple(code for code in TIER1_CODES if not self.results[code])


def _check_required_fields(piece: PieceArtifact, banned_phrases: Sequence[str]) -> list[Violation]:
    """Run I2 for one Piece: required fields plus the piece guardrails.

    Args:
        piece: The Piece to check.
        banned_phrases: The banned-filler list for the embedded piece checks.

    Returns:
        I2 violations for this Piece.
    """
    violations: list[Violation] = []
    missing = [
        name
        for name, value in (
            ("id", piece.id),
            ("title", piece.title),
            ("teaser", piece.teaser),
        )
        if not value.strip()
    ]
    if piece.read_time_min < 1:
        missing.append("readTimeMin")
    if not piece.topic_ids:
        missing.append("topics")
    if not piece.blocks:
        missing.append("body")
    if missing:
        violations.append(
            Violation(
                code="I2",
                subject=piece.id or "<unidentified piece>",
                message=f"missing required fields: {', '.join(missing)}",
            )
        )
    piece_failures = evaluate_piece(piece, banned_phrases)
    if piece_failures:
        codes = ", ".join(sorted({violation.code for violation in piece_failures}))
        violations.append(
            Violation(
                code="I2",
                subject=piece.id,
                message=f"fails piece guardrails: {codes}",
            )
        )
    return violations


def _check_ledger(piece_id: str, ledger: GroundingLedger | None) -> list[Violation]:
    """Run I8 for one Piece's grounding ledger.

    Args:
        piece_id: The Piece the ledger should ground.
        ledger: The ledger, or None if the run never produced one.

    Returns:
        I8 violations for this Piece.
    """
    if ledger is None:
        return [Violation(code="I8", subject=piece_id, message="no grounding ledger")]
    violations: list[Violation] = []
    if not ledger.claims:
        violations.append(Violation(code="I8", subject=piece_id, message="empty grounding ledger"))
    for claim in ledger.claims:
        if claim.status is ClaimStatus.VERIFIED:
            if not claim.sources:
                violations.append(
                    Violation(
                        code="I8",
                        subject=piece_id,
                        message=f"verified claim {claim.id!r} has no backing source",
                    )
                )
            if claim.refutation is None:
                violations.append(
                    Violation(
                        code="I8",
                        subject=piece_id,
                        message=f"verified claim {claim.id!r} never faced the refutation round",
                    )
                )
        elif claim.load_bearing:
            violations.append(
                Violation(
                    code="I8",
                    subject=piece_id,
                    message=f"load-bearing claim {claim.id!r} is {claim.status}, not verified",
                )
            )
    return violations


def _connected(piece_ids: frozenset[str], edges: Sequence[tuple[str, str]]) -> bool:
    """Decide I7: is the constellation one connected component (undirected)?

    Args:
        piece_ids: Every Piece in the constellation.
        edges: The (from, to) pairs whose endpoints both exist.

    Returns:
        True if every Piece is reachable from any other, or the set is
        empty or a singleton.
    """
    if len(piece_ids) <= 1:
        return True
    neighbours: dict[str, set[str]] = {piece_id: set() for piece_id in piece_ids}
    for origin, destination in edges:
        neighbours[origin].add(destination)
        neighbours[destination].add(origin)
    start = next(iter(sorted(piece_ids)))
    seen = {start}
    frontier = [start]
    while frontier:
        current = frontier.pop()
        for neighbour in neighbours[current]:
            if neighbour not in seen:
                seen.add(neighbour)
                frontier.append(neighbour)
    return seen == set(piece_ids)


def evaluate_constellation(
    constellation: ConstellationArtifact, banned_phrases: Sequence[str]
) -> Tier1Report:
    """Assert the Tier-1 outcome contract I1–I8, binary per invariant.

    A cross-Topic Connection (I6) is an outbound edge whose destination
    carries at least one Topic the origin does not — so a broad spine Piece
    can still satisfy I6 by pointing somewhere that adds a Topic.

    Args:
        constellation: The assembled run output.
        banned_phrases: The banned-filler list for the embedded checks.

    Returns:
        The binary per-invariant results and their specific violations.
    """
    violations: list[Violation] = []
    pieces = tuple(constellation.pieces)
    piece_ids = constellation.piece_ids()
    topics_by_piece = constellation.topics_by_piece()

    low, high = constellation.piece_count_target
    if not low <= len(pieces) <= high:
        violations.append(
            Violation(
                code="I1",
                subject="constellation",
                message=f"piece count {len(pieces)} misses the Brief target [{low}, {high}]",
            )
        )

    for piece in pieces:
        violations.extend(_check_required_fields(piece, banned_phrases))

    covered = frozenset().union(*topics_by_piece.values()) if topics_by_piece else frozenset()
    uncovered = [tid for tid in constellation.target_topic_ids if tid not in covered]
    if uncovered:
        violations.append(
            Violation(
                code="I3",
                subject="constellation",
                message=f"target Topics not covered: {', '.join(uncovered)}",
            )
        )

    outbound: dict[str, list[str]] = {piece_id: [] for piece_id in piece_ids}
    resolvable_edges: list[tuple[str, str]] = []
    for connection in constellation.connections:
        unresolved = [
            end
            for end in (connection.from_piece_id, connection.to_piece_id)
            if end not in piece_ids
        ]
        if unresolved:
            violations.append(
                Violation(
                    code="I5",
                    subject=connection.subject(),
                    message=f"Connection endpoint(s) missing from constellation: "
                    f"{', '.join(unresolved)}",
                )
            )
            continue
        outbound[connection.from_piece_id].append(connection.to_piece_id)
        resolvable_edges.append((connection.from_piece_id, connection.to_piece_id))

    hook_failures = evaluate_connections(constellation.connections, banned_phrases)
    if hook_failures:
        codes = ", ".join(sorted({violation.code for violation in hook_failures}))
        violations.append(
            Violation(
                code="I5",
                subject="constellation",
                message=f"Connections fail connection guardrails: {codes}",
            )
        )

    for piece in pieces:
        if not outbound[piece.id]:
            violations.append(
                Violation(
                    code="I4",
                    subject=piece.id,
                    message="dead end — no outbound Connection",
                )
            )
        else:
            origin_topics = topics_by_piece[piece.id]
            if not any(
                topics_by_piece[destination] - origin_topics for destination in outbound[piece.id]
            ):
                violations.append(
                    Violation(
                        code="I6",
                        subject=piece.id,
                        message="no outbound Connection reaches a different Topic",
                    )
                )

    if not _connected(piece_ids, resolvable_edges):
        violations.append(
            Violation(
                code="I7",
                subject="constellation",
                message="the constellation is not a single connected graph",
            )
        )

    for piece in pieces:
        violations.extend(_check_ledger(piece.id, constellation.ledgers.get(piece.id)))

    failed = {violation.code for violation in violations}
    results = {code: code not in failed for code in TIER1_CODES}
    return Tier1Report(
        results=results,
        violations=tuple(sorted(violations, key=lambda v: (v.code, v.subject, v.message))),
    )

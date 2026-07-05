"""Constellation evaluator — the Tier-1 outcome contract I1–I8, binary."""

from content_graph.domain.blocks import BlockKind, ContentBlock
from harness.domain.artifacts import ConstellationArtifact, PieceArtifact, WiredConnection
from harness.domain.grounding import (
    ClaimRecord,
    ClaimStatus,
    GroundingLedger,
    RefutationVerdict,
    SourceRecord,
    SourceTier,
)
from harness.guardrails.constellation import TIER1_CODES, evaluate_constellation

OPENING = (
    "On 26 April 1956, the Ideal-X left Newark with 58 aluminium boxes bolted "
    "to its deck, and Malcom McLean watched from the pier."
)
BODY = (
    "By 1966 a container crossing cost one-sixteenth of loose cargo; the "
    "longshoremen of Manhattan lost 30,000 jobs in a decade."
)


def make_piece(piece_id: str, topic: str) -> PieceArtifact:
    return PieceArtifact(
        id=piece_id,
        title=f"Title for {piece_id}",
        teaser=f"A teaser that pitches {piece_id} cold.",
        read_time_min=4,
        topic_ids=(topic,),
        blocks=(
            ContentBlock(kind=BlockKind.PARAGRAPH, payload={"text": OPENING}),
            ContentBlock(kind=BlockKind.PARAGRAPH, payload={"text": BODY}),
        ),
    )


def make_ledger(piece_id: str) -> GroundingLedger:
    return GroundingLedger(
        piece_id=piece_id,
        claims=(
            ClaimRecord(
                id=f"{piece_id}-c1",
                text="The Ideal-X sailed on 26 April 1956 with 58 containers.",
                tier=SourceTier.PRIMARY,
                status=ClaimStatus.VERIFIED,
                sources=(
                    SourceRecord(
                        citation="https://example.org/port-authority-1956",
                        tier=SourceTier.PRIMARY,
                        credibility="Port Newark shipping record",
                        excerpt="58 loaded containers departed 26 April 1956.",
                        retrieved_at="2026-07-01T00:00:00Z",
                    ),
                ),
                refutation=RefutationVerdict.SURVIVED,
            ),
        ),
    )


def hook_for(from_id: str, to_id: str) -> str:
    return f"What {from_id} never tells you about {to_id} — until the money moves?"


def rationale_for(from_id: str, to_id: str) -> str:
    return (
        f"The 1956 cost collapse traced in {from_id} is the direct cause of the "
        f"shift described in {to_id}."
    )


def make_edge(from_id: str, to_id: str) -> WiredConnection:
    return WiredConnection(
        from_piece_id=from_id,
        to_piece_id=to_id,
        hook=hook_for(from_id, to_id),
        rationale=rationale_for(from_id, to_id),
    )


def make_constellation(
    pieces: tuple[PieceArtifact, ...] | None = None,
    connections: tuple[WiredConnection, ...] | None = None,
    with_ledgers: bool = True,
    target: tuple[int, int] = (3, 3),
    topics: tuple[str, ...] = ("shipping", "economics", "geography"),
) -> ConstellationArtifact:
    if pieces is None:
        pieces = (
            make_piece("a", "shipping"),
            make_piece("b", "economics"),
            make_piece("c", "geography"),
        )
    if connections is None:
        connections = (
            make_edge("a", "b"),
            make_edge("b", "c"),
            make_edge("c", "a"),
        )
    ledgers = {piece.id: make_ledger(piece.id) for piece in pieces} if with_ledgers else {}
    return ConstellationArtifact(
        pieces=pieces,
        connections=connections,
        ledgers=ledgers,
        piece_count_target=target,
        target_topic_ids=topics,
    )


def test_valid_constellation_passes_all_tier1():
    report = evaluate_constellation(make_constellation(), ())
    assert report.passed
    assert report.results == dict.fromkeys(TIER1_CODES, True)


def test_results_are_binary_booleans():
    report = evaluate_constellation(make_constellation(), ())
    assert all(isinstance(value, bool) for value in report.results.values())


def test_dead_end_fails_i4():
    constellation = make_constellation(
        connections=(make_edge("a", "b"), make_edge("b", "a"), make_edge("b", "c"))
    )
    report = evaluate_constellation(constellation, ())
    assert report.results["I4"] is False
    assert any(v.code == "I4" and v.subject == "c" for v in report.violations)


def test_connection_to_missing_piece_fails_i5():
    constellation = make_constellation(
        connections=(make_edge("a", "b"), make_edge("b", "c"), make_edge("c", "ghost"))
    )
    report = evaluate_constellation(constellation, ())
    assert report.results["I5"] is False


def test_no_cross_topic_outbound_fails_i6():
    pieces = (
        make_piece("a", "shipping"),
        make_piece("a2", "shipping"),
        make_piece("b", "economics"),
    )
    constellation = make_constellation(
        pieces=pieces,
        connections=(make_edge("a", "a2"), make_edge("a2", "b"), make_edge("b", "a")),
        topics=("shipping", "economics"),
    )
    report = evaluate_constellation(constellation, ())
    assert report.results["I6"] is False
    assert any(v.code == "I6" and v.subject == "a" for v in report.violations)


def test_disconnected_graph_fails_i7():
    pieces = (
        make_piece("a", "shipping"),
        make_piece("b", "economics"),
        make_piece("c", "geography"),
        make_piece("d", "finance"),
    )
    constellation = make_constellation(
        pieces=pieces,
        connections=(
            make_edge("a", "b"),
            make_edge("b", "a"),
            make_edge("c", "d"),
            make_edge("d", "c"),
        ),
        target=(4, 4),
        topics=("shipping", "economics", "geography", "finance"),
    )
    report = evaluate_constellation(constellation, ())
    assert report.results["I7"] is False


def test_piece_count_miss_fails_i1():
    report = evaluate_constellation(make_constellation(target=(5, 6)), ())
    assert report.results["I1"] is False


def test_uncovered_target_topic_fails_i3():
    report = evaluate_constellation(
        make_constellation(topics=("shipping", "economics", "geography", "warfare")), ()
    )
    assert report.results["I3"] is False


def test_missing_required_field_fails_i2():
    broken = PieceArtifact(id="a", title="", teaser="", read_time_min=0)
    constellation = make_constellation(
        pieces=(broken, make_piece("b", "economics"), make_piece("c", "geography"))
    )
    report = evaluate_constellation(constellation, ())
    assert report.results["I2"] is False


def test_sloppy_piece_prose_fails_i2():
    sloppy = PieceArtifact(
        id="a",
        title="Title",
        teaser="Teaser.",
        read_time_min=4,
        topic_ids=("shipping",),
        blocks=(
            ContentBlock(
                kind=BlockKind.PARAGRAPH,
                payload={"text": "A container is a standard box for moving goods."},
            ),
        ),
    )
    constellation = make_constellation(
        pieces=(sloppy, make_piece("b", "economics"), make_piece("c", "geography"))
    )
    report = evaluate_constellation(constellation, ())
    assert report.results["I2"] is False


def test_missing_ledger_fails_i8():
    report = evaluate_constellation(make_constellation(with_ledgers=False), ())
    assert report.results["I8"] is False


def test_verified_claim_without_refutation_round_fails_i8():
    pieces = (
        make_piece("a", "shipping"),
        make_piece("b", "economics"),
        make_piece("c", "geography"),
    )
    ledgers = {piece.id: make_ledger(piece.id) for piece in pieces}
    unrefuted = ClaimRecord(
        id="a-c2",
        text="Trucking rates fell 25 percent by 1960.",
        tier=SourceTier.SECONDARY,
        status=ClaimStatus.VERIFIED,
        sources=(
            SourceRecord(citation="https://example.org/x", tier=SourceTier.SECONDARY),
            SourceRecord(citation="https://example.net/y", tier=SourceTier.SECONDARY),
        ),
        refutation=None,
    )
    ledgers["a"] = GroundingLedger(piece_id="a", claims=(*ledgers["a"].claims, unrefuted))
    constellation = ConstellationArtifact(
        pieces=pieces,
        connections=(make_edge("a", "b"), make_edge("b", "c"), make_edge("c", "a")),
        ledgers=ledgers,
        piece_count_target=(3, 3),
        target_topic_ids=("shipping", "economics", "geography"),
    )
    report = evaluate_constellation(constellation, ())
    assert report.results["I8"] is False


def test_unverified_load_bearing_claim_fails_i8():
    pieces = (
        make_piece("a", "shipping"),
        make_piece("b", "economics"),
        make_piece("c", "geography"),
    )
    ledgers = {piece.id: make_ledger(piece.id) for piece in pieces}
    flagged = ClaimRecord(
        id="a-c3",
        text="McLean personally invented the twist-lock.",
        tier=SourceTier.TERTIARY,
        status=ClaimStatus.FLAGGED,
        load_bearing=True,
        internal_only=True,
    )
    ledgers["a"] = GroundingLedger(piece_id="a", claims=(*ledgers["a"].claims, flagged))
    constellation = ConstellationArtifact(
        pieces=pieces,
        connections=(make_edge("a", "b"), make_edge("b", "c"), make_edge("c", "a")),
        ledgers=ledgers,
        piece_count_target=(3, 3),
        target_topic_ids=("shipping", "economics", "geography"),
    )
    report = evaluate_constellation(constellation, ())
    assert report.results["I8"] is False


def test_failed_codes_lists_only_failures():
    constellation = make_constellation(
        connections=(make_edge("a", "b"), make_edge("b", "a"), make_edge("b", "c"))
    )
    report = evaluate_constellation(constellation, ())
    assert "I4" in report.failed_codes()
    assert "I1" not in report.failed_codes()

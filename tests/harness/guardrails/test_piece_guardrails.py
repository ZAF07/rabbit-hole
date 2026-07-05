"""Piece guardrail evaluator — crafted fixtures assert the specific violation code."""

from content_graph.domain.blocks import BlockKind, ContentBlock
from harness.domain.artifacts import PieceArtifact
from harness.guardrails.piece import evaluate_piece

CONCRETE_OPENING = (
    "On 14 April 1912, Harold Bride was half asleep when the Titanic's hull "
    "shuddered beneath his bunk in the wireless cabin."
)
CONCRETE_MIDDLE = (
    "Bride and Jack Phillips kept transmitting for two hours; the CQD calls "
    "reached the Carpathia 58 miles away, which turned at 17 knots."
)


def paragraph(text: str) -> ContentBlock:
    return ContentBlock(kind=BlockKind.PARAGRAPH, payload={"text": text})


def make_piece(*paragraphs: str, piece_id: str = "p1") -> PieceArtifact:
    return PieceArtifact(
        id=piece_id,
        title="The Night the Wireless Went Silent",
        teaser="Two operators, one iceberg, and the birth of radio law.",
        read_time_min=5,
        topic_ids=("maritime-history",),
        blocks=tuple(paragraph(text) for text in paragraphs),
    )


def codes(piece: PieceArtifact, banned: tuple[str, ...] = ()) -> set[str]:
    return {violation.code for violation in evaluate_piece(piece, banned)}


def test_opening_on_a_definition_fails_a1():
    piece = make_piece(
        "A semaphore is a system for conveying information by visual signals.",
        CONCRETE_MIDDLE,
    )
    assert "A1" in codes(piece)


def test_dictionary_move_opening_fails_a1():
    piece = make_piece(
        "The term 'wireless telegraphy' refers to the transmission of signals without wires.",
        CONCRETE_MIDDLE,
    )
    assert "A1" in codes(piece)


def test_concrete_scene_opening_passes_a1():
    piece = make_piece(CONCRETE_OPENING, CONCRETE_MIDDLE)
    assert "A1" not in codes(piece)


def test_warmup_phrase_in_opening_fails_a2():
    piece = make_piece(
        "Have you ever wondered what happens when a ship sinks at night? "
        "The answer arrived on 14 April 1912.",
        CONCRETE_MIDDLE,
    )
    assert "A2" in codes(piece)


def test_pure_abstraction_paragraph_fails_b1():
    piece = make_piece(
        CONCRETE_OPENING,
        "The nature of progress is always contested. Change brings uncertainty, "
        "and uncertainty breeds resistance among those who benefit from the way "
        "things already are.",
    )
    assert "B1" in codes(piece)


def test_concrete_paragraph_passes_b1():
    piece = make_piece(CONCRETE_OPENING, CONCRETE_MIDDLE)
    assert "B1" not in codes(piece)


def test_short_transition_paragraph_is_exempt_from_b1():
    piece = make_piece(CONCRETE_OPENING, "Then everything changed.", CONCRETE_MIDDLE)
    assert "B1" not in codes(piece)


def test_banned_filler_phrase_fails_d3():
    piece = make_piece(
        CONCRETE_OPENING,
        "The disaster was a game-changer for maritime regulation in 1913.",
    )
    assert "D3" in codes(piece, banned=("game-changer",))


def test_wildcard_banned_phrase_matches_gap():
    piece = make_piece(
        CONCRETE_OPENING,
        "In an increasingly connected world, the 1912 rules still bind ships today.",
    )
    assert "D3" in codes(piece, banned=("In an increasingly ___ world",))


def test_real_banned_list_catches_delve(banned_phrases):
    piece = make_piece(
        CONCRETE_OPENING,
        "Investigators would delve into the wreck for decades after 1912.",
    )
    assert "D3" in codes(piece, banned=banned_phrases)


def test_hedging_mush_fails_d2():
    piece = make_piece(
        CONCRETE_OPENING,
        "Many experts believe the iceberg field of 1912 was unusually dense that spring.",
    )
    assert "D2" in codes(piece)


def test_listicle_scaffolding_fails_d1():
    piece = make_piece(
        CONCRETE_OPENING,
        "Here are the three reasons why the Titanic's 2,224 passengers were doomed.",
    )
    assert "D1" in codes(piece)


def test_empty_conclusion_fails_d5():
    piece = make_piece(
        CONCRETE_OPENING,
        CONCRETE_MIDDLE,
        "In conclusion, the sinking of 1912 changed radio law forever.",
    )
    assert "D5" in codes(piece)


def test_definitional_frame_after_heading_fails_d6():
    piece = PieceArtifact(
        id="p1",
        title="The Night the Wireless Went Silent",
        teaser="Two operators, one iceberg.",
        read_time_min=5,
        topic_ids=("maritime-history",),
        blocks=(
            paragraph(CONCRETE_OPENING),
            ContentBlock(kind=BlockKind.HEADING, payload={"text": "The Law", "level": 2}),
            paragraph(
                "The Radio Act is a statute that Congress passed in 1912 to govern "
                "wireless operators at sea."
            ),
        ),
    )
    assert "D6" in {v.code for v in evaluate_piece(piece, ())}


def test_adjective_stacking_fails_d9():
    piece = make_piece(
        CONCRETE_OPENING,
        "The rescue of 1912 was incredibly dramatic, truly remarkable in the "
        "annals of the North Atlantic.",
    )
    assert "D9" in codes(piece)


def test_clean_piece_has_no_violations(banned_phrases):
    piece = make_piece(CONCRETE_OPENING, CONCRETE_MIDDLE)
    assert evaluate_piece(piece, banned_phrases) == ()


def test_evaluator_is_pure_and_deterministic(banned_phrases):
    piece = make_piece(
        "A semaphore is a system for conveying information.",
        "The nature of progress is always contested by those who fear change and "
        "cling to whatever arrangement currently rewards them the most.",
    )
    first = evaluate_piece(piece, banned_phrases)
    second = evaluate_piece(piece, banned_phrases)
    assert first == second


def test_violations_carry_the_offending_excerpt():
    piece = make_piece("A semaphore is a system for conveying information.", CONCRETE_MIDDLE)
    a1 = [v for v in evaluate_piece(piece, ()) if v.code == "A1"]
    assert a1 and "semaphore" in (a1[0].excerpt or "")

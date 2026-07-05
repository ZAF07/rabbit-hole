"""Piece-level anti-slop checks (``harness/guardrails/piece.md``) as pure functions.

Implements every check that is mechanically decidable as a binary FAIL-if
rule. Checks that require judgment are enumerated in
:data:`JUDGED_PIECE_CHECKS` and are applied by the Editor's machine-QA LLM
judge (Stage 4), never here — this module stays deterministic and offline.
"""

import re
from collections.abc import Mapping, Sequence

from content_graph.domain.blocks import BlockKind
from harness.domain.artifacts import PieceArtifact, block_text
from harness.guardrails.phrases import compile_phrase
from harness.guardrails.violations import Violation

JUDGED_PIECE_CHECKS: Mapping[str, str] = {
    "A3": "reason-to-care by sentence 3 — tension, stakes, or surprise",
    "B2": "no padding — no sentence cuttable without loss",
    "B3": "show the number — no magnitude word where a figure exists",
    "C1": "delivers a non-obvious payoff (reframe or vivid new understanding)",
    "C2": "the reframe is earned and discovered, not announced",
    "C3": "real insight, not a truism or circularity",
    "D4": "no AI-summary cadence — rhythmically varied paragraphs",
    "D7": "no both-sides mush dodging a supported position",
    "D8": "no over-explaining what a curious adult already knows",
    "E1": "dinner-party test — something specific to say tonight",
    "E2": "ends on a doorway — the close opens outward",
    "F1": "matches the active Voice Profile; its Don'ts are hard fails",
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_DEFINITIONAL_OPEN = re.compile(
    r"^(?:the\s|a\s|an\s)?[\w\s',-]{1,60}?\b(?:is|are)\s+(?:a|an|the)\s+\w+", re.IGNORECASE
)
_DICTIONARY_MOVES = (
    "is defined as",
    "are defined as",
    "refers to",
    "refer to",
    "is the term for",
    "the dictionary defines",
)
_WARMUP_PHRASES = (
    "in today's world",
    "in an increasingly",
    "have you ever wondered",
    "since the dawn of",
    "more than ever before",
    "picture this",
    "throughout history",
)
_LISTICLE = re.compile(
    r"\b(?:\d+|three|four|five|six|seven|several|many)\s+"
    r"(?:reasons|ways|things|lessons|facts)\b|\bhere are\b",
    re.IGNORECASE,
)
_HEDGES = (
    "many experts believe",
    "experts believe",
    "it could be argued",
    "some say",
    "some argue",
    "arguably",
)
_EMPTY_CONCLUSIONS = (
    "in conclusion",
    "all in all",
    "at the end of the day",
    "when all is said and done",
)
_DEFINITIONAL_FRAME = re.compile(
    r"^[A-Z][\w\s',-]{0,60}\b(?:is|are)\s+(?:a|an)\s+[\w\s,'-]{0,60}\b(?:that|which)\b"
)
_INTENSIFIERS = (
    "incredibly",
    "truly",
    "absolutely",
    "remarkably",
    "utterly",
    "extremely",
    "amazingly",
    "astonishingly",
    "stunningly",
    "undeniably",
)
_ADJECTIVE_STACK = re.compile(
    rf"\b(?:{'|'.join(_INTENSIFIERS)})\s+\w+[,\s]+(?:and\s+)?"
    rf"(?:{'|'.join(_INTENSIFIERS)})\s+\w+",
    re.IGNORECASE,
)
_QUOTED_SPAN = re.compile(r"[\"“”'‘’][^\"“”]{3,}[\"“”'‘’]")
_TRANSITION_MAX_CHARS = 90


def _sentences(text: str) -> list[str]:
    """Split prose into sentences, approximately.

    Args:
        text: The prose to split.

    Returns:
        The non-empty sentences.
    """
    return [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]


def _has_concrete_detail(paragraph: str) -> bool:
    """Decide whether a paragraph carries a checkable concrete detail (B1).

    A digit, a quoted span, or a proper noun (a capitalized word that is not
    sentence-initial) all count.

    Args:
        paragraph: The paragraph text.

    Returns:
        True if a concrete detail was found.
    """
    if any(char.isdigit() for char in paragraph):
        return True
    if _QUOTED_SPAN.search(paragraph):
        return True
    for sentence in _sentences(paragraph):
        words = sentence.split()
        for word in words[1:]:
            stripped = word.strip("\"'“”‘’(),.;:!?—-")
            if stripped and stripped[0].isupper() and stripped not in {"I"}:
                return True
    return False


def _check_opening(piece: PieceArtifact) -> list[Violation]:
    """Run the A-family opening checks on the first paragraph.

    Args:
        piece: The Piece under review.

    Returns:
        A1/A2 violations found in the opening.
    """
    violations: list[Violation] = []
    paragraphs = piece.paragraphs()
    if not paragraphs:
        return violations
    opening = paragraphs[0]
    sentences = _sentences(opening)
    if sentences:
        first = sentences[0]
        lowered = first.lower()
        if _DEFINITIONAL_OPEN.match(first) or any(move in lowered for move in _DICTIONARY_MOVES):
            violations.append(
                Violation(
                    code="A1",
                    subject=piece.id,
                    message="opens on a definition or dictionary move, not a concrete scene",
                    excerpt=first,
                )
            )
    head = " ".join(sentences[:3]).lower()
    for phrase in _WARMUP_PHRASES:
        if phrase in head:
            violations.append(
                Violation(
                    code="A2",
                    subject=piece.id,
                    message="throat-clearing warm-up phrase in the opening",
                    excerpt=phrase,
                )
            )
    return violations


def _check_paragraph_density(piece: PieceArtifact) -> list[Violation]:
    """Run B1 over every paragraph block.

    Args:
        piece: The Piece under review.

    Returns:
        One B1 violation per abstraction-only paragraph.
    """
    violations: list[Violation] = []
    for paragraph in piece.paragraphs():
        if len(paragraph) <= _TRANSITION_MAX_CHARS:
            continue
        if not _has_concrete_detail(paragraph):
            violations.append(
                Violation(
                    code="B1",
                    subject=piece.id,
                    message="paragraph of pure abstraction — no name, date, number, or object",
                    excerpt=paragraph[:120],
                )
            )
    return violations


def _check_slop_tells(piece: PieceArtifact, banned_phrases: Sequence[str]) -> list[Violation]:
    """Run the D-family instant-detect checks over the whole prose surface.

    Args:
        piece: The Piece under review.
        banned_phrases: The D3 banned-filler list.

    Returns:
        D1/D2/D3/D5/D6/D9 violations.
    """
    violations: list[Violation] = []
    text = piece.all_text()
    lowered = text.lower()

    listicle = _LISTICLE.search(text)
    if listicle:
        violations.append(
            Violation(
                code="D1",
                subject=piece.id,
                message="listicle argument scaffolding",
                excerpt=listicle.group(0),
            )
        )
    for hedge in _HEDGES:
        if hedge in lowered:
            violations.append(
                Violation(
                    code="D2",
                    subject=piece.id,
                    message="hedging mush used to dodge a claim — ground it or cut it",
                    excerpt=hedge,
                )
            )
    for phrase in banned_phrases:
        if compile_phrase(phrase).search(text):
            violations.append(
                Violation(
                    code="D3",
                    subject=piece.id,
                    message="banned-filler phrase",
                    excerpt=phrase,
                )
            )
    paragraphs = piece.paragraphs()
    if paragraphs:
        closing = paragraphs[-1].lower()
        for phrase in _EMPTY_CONCLUSIONS:
            if phrase in closing:
                violations.append(
                    Violation(
                        code="D5",
                        subject=piece.id,
                        message="empty restating conclusion",
                        excerpt=phrase,
                    )
                )
    for section_opener in _section_openers(piece):
        if _DEFINITIONAL_FRAME.match(section_opener):
            violations.append(
                Violation(
                    code="D6",
                    subject=piece.id,
                    message="Wikipedia-style 'X is a Y that…' used to open a section",
                    excerpt=section_opener[:120],
                )
            )
    stack = _ADJECTIVE_STACK.search(text)
    if stack:
        violations.append(
            Violation(
                code="D9",
                subject=piece.id,
                message="stacked empty intensifiers",
                excerpt=stack.group(0),
            )
        )
    return violations


def _section_openers(piece: PieceArtifact) -> list[str]:
    """Return the first paragraph after each heading block (D6's targets).

    Args:
        piece: The Piece under review.

    Returns:
        The section-opening paragraph texts.
    """
    openers: list[str] = []
    blocks = tuple(piece.blocks)
    for index, block in enumerate(blocks[:-1]):
        if block.kind is BlockKind.HEADING and blocks[index + 1].kind is BlockKind.PARAGRAPH:
            openers.append(block_text(blocks[index + 1]))
    return openers


def evaluate_piece(piece: PieceArtifact, banned_phrases: Sequence[str]) -> tuple[Violation, ...]:
    """Run every mechanical piece-level guardrail check.

    Pure and deterministic: the same artifact and phrase list always yield
    the same violations, in code order.

    Args:
        piece: The Piece artifact (draft or final) to judge.
        banned_phrases: The D3 banned-filler list, typically parsed from
            ``harness/guardrails/piece.md`` via
            :func:`harness.guardrails.phrases.parse_banned_phrases`.

    Returns:
        Every violation found, sorted by code then message.
    """
    violations = [
        *_check_opening(piece),
        *_check_paragraph_density(piece),
        *_check_slop_tells(piece, banned_phrases),
    ]
    return tuple(sorted(violations, key=lambda v: (v.code, v.message, v.excerpt or "")))

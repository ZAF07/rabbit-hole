"""The Theme Brief — the single human input that seeds one run (``goal.md``).

Ephemeral generation input, never a stored domain entity (ADR 0006). Stage 0
gates on it: a Brief with any unfilled ``<placeholder>`` fails the gate
before the Architect runs.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from harness.domain.frontmatter import split_frontmatter
from harness.errors import BriefValidationError

_PLACEHOLDER = re.compile(r"<[^<>\n]{1,120}>")
_RANGE = re.compile(r"^(\d+)\s*[-–—]\s*(\d+)$")


@dataclass(frozen=True)
class ThemeBrief:
    """The parsed Theme Brief.

    Attributes:
        through_line: The editorial spine of the run.
        target_topics: The Topics the constellation must span (feeds I3).
        piece_count: Inclusive (min, max) target Piece count (feeds I1).
        seed_sources: Human-curated references, trusted tier but still vetted.
        must_include: Angles the Architect must place in the plan.
        entry_hints: Angles that should open cold as a Daily Feature (J3).
        must_avoid: Framings to keep out of the plan.
        voice: Per-run Voice Profile name, or None for the active default.
        notes: Free prose to the Architect.
    """

    through_line: str
    target_topics: Sequence[str]
    piece_count: tuple[int, int]
    seed_sources: Sequence[str] = field(default_factory=tuple)
    must_include: Sequence[str] = field(default_factory=tuple)
    entry_hints: Sequence[str] = field(default_factory=tuple)
    must_avoid: Sequence[str] = field(default_factory=tuple)
    voice: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        """Normalize list fields to tuples."""
        for name in ("target_topics", "seed_sources", "must_include", "entry_hints", "must_avoid"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


def find_placeholders(text: str) -> tuple[str, ...]:
    """Find unfilled ``<placeholder>`` spans in a deliverable's raw text.

    Args:
        text: The raw file text.

    Returns:
        Every placeholder found, in document order.
    """
    return tuple(match.group(0) for match in _PLACEHOLDER.finditer(text))


def _parse_count(raw: str) -> tuple[int, int]:
    """Parse the ``piece_count`` field — a number or a small range.

    Args:
        raw: The field value, e.g. ``"30"`` or ``"28–32"``.

    Returns:
        The inclusive (min, max) target.

    Raises:
        BriefValidationError: If the value is not a positive count or range.
    """
    text = raw.strip()
    ranged = _RANGE.match(text)
    if ranged:
        low, high = int(ranged.group(1)), int(ranged.group(2))
    elif text.isdigit():
        low = high = int(text)
    else:
        raise BriefValidationError(f"piece_count must be a number or range, got {raw!r}")
    if low < 1 or high < low:
        raise BriefValidationError(f"piece_count range [{low}, {high}] is not usable")
    return low, high


def parse_brief(text: str) -> ThemeBrief:
    """Parse and validate a Theme Brief from its ``goal.md`` text.

    Args:
        text: The raw file text.

    Returns:
        The validated Brief.

    Raises:
        BriefValidationError: If a placeholder is unfilled or a required
            field (through_line, target_topics, piece_count) is missing.
    """
    placeholders = find_placeholders(text)
    if placeholders:
        raise BriefValidationError(f"Brief has unfilled placeholders: {', '.join(placeholders)}")
    fields, body = split_frontmatter(text)

    through_line = fields.get("through_line", "")
    if not isinstance(through_line, str) or not through_line.strip():
        raise BriefValidationError("Brief requires a through_line")
    topics = fields.get("target_topics", [])
    if not isinstance(topics, list) or not topics:
        raise BriefValidationError("Brief requires target_topics")
    raw_count = fields.get("piece_count", "")
    if not isinstance(raw_count, str) or not raw_count.strip():
        raise BriefValidationError("Brief requires piece_count")

    def list_field(name: str) -> tuple[str, ...]:
        """Read an optional list field.

        Args:
            name: The field name.

        Returns:
            The items, or an empty tuple.
        """
        value = fields.get(name, [])
        return tuple(value) if isinstance(value, list) else (value,)

    voice = fields.get("voice")
    return ThemeBrief(
        through_line=through_line.strip(),
        target_topics=tuple(topics),
        piece_count=_parse_count(raw_count),
        seed_sources=list_field("seed_sources"),
        must_include=list_field("must_include"),
        entry_hints=list_field("entry_hints"),
        must_avoid=list_field("must_avoid"),
        voice=voice if isinstance(voice, str) and voice.strip() else None,
        notes=body,
    )

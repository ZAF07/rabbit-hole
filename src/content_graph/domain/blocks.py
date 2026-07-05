"""Content Blocks — the small, fixed vocabulary a Piece's body is made of.

The vocabulary is deliberately fixed: every kind is both a renderer commitment
and a QA rule, which is what lets the generation harness assert a Piece's
visual rhythm. V1 validates and populates the four text kinds only; the three
visual kinds are reserved slots that are never written (ADR 0007).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from content_graph.domain.errors import BlockValidationError, ReservedBlockKindError


class BlockKind(StrEnum):
    """Every kind of Content Block, including the V1-reserved visual kinds."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    PULL_QUOTE = "pull-quote"
    STAT_CALLOUT = "stat-callout"
    IMAGE = "image"
    GIF = "gif"
    DIAGRAM = "diagram"


TEXT_KINDS: frozenset[BlockKind] = frozenset(
    {BlockKind.HEADING, BlockKind.PARAGRAPH, BlockKind.PULL_QUOTE, BlockKind.STAT_CALLOUT}
)

VISUAL_KINDS: frozenset[BlockKind] = frozenset({BlockKind.IMAGE, BlockKind.GIF, BlockKind.DIAGRAM})


def _require_text(payload: Mapping[str, object], key: str, kind: BlockKind) -> None:
    """Assert that ``payload[key]`` is a non-empty string.

    Args:
        payload: The block payload under validation.
        key: The required field name.
        kind: The block kind, for the error message.

    Raises:
        BlockValidationError: If the field is missing, not a string, or blank.
    """
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BlockValidationError(f"{kind} block requires a non-empty string {key!r}")


def _validate_payload(kind: BlockKind, payload: Mapping[str, object]) -> None:
    """Validate a payload against the contract for its kind.

    Args:
        kind: The block kind whose contract applies.
        payload: The payload to validate.

    Raises:
        ReservedBlockKindError: If the kind is a V1-reserved visual kind.
        BlockValidationError: If a required field is missing or mistyped.
    """
    if kind in VISUAL_KINDS:
        raise ReservedBlockKindError(
            f"block kind {kind!r} is reserved for future visuals and is never written in V1"
        )
    if kind is BlockKind.HEADING:
        _require_text(payload, "text", kind)
        level = payload.get("level")
        if not isinstance(level, int) or isinstance(level, bool) or level < 1:
            raise BlockValidationError("heading block requires an integer 'level' >= 1")
    elif kind is BlockKind.PARAGRAPH:
        _require_text(payload, "text", kind)
    elif kind is BlockKind.PULL_QUOTE:
        _require_text(payload, "text", kind)
        attribution = payload.get("attribution")
        if attribution is not None and not isinstance(attribution, str):
            raise BlockValidationError("pull-quote 'attribution' must be a string when present")
    elif kind is BlockKind.STAT_CALLOUT:
        value = payload.get("value")
        if not isinstance(value, str | int | float) or isinstance(value, bool):
            raise BlockValidationError("stat-callout block requires a 'value' (string or number)")
        _require_text(payload, "label", kind)


@dataclass(frozen=True)
class ContentBlock:
    """One element of a Piece's ordered body.

    Attributes:
        kind: Which member of the fixed block vocabulary this is.
        payload: The kind-specific fields (validated at construction).
    """

    kind: BlockKind
    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Freeze a defensive copy of the payload and validate it.

        Raises:
            ReservedBlockKindError: If the kind is a V1-reserved visual kind.
            BlockValidationError: If the payload violates the kind's contract.
        """
        object.__setattr__(self, "payload", dict(self.payload))
        _validate_payload(self.kind, self.payload)

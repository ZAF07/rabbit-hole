"""The Architect's plan — Piece concepts + the full Connection skeleton.

``plan.md`` is the moat made reviewable: the whole constellation designed
before any prose exists, in a strict-but-editable markdown grammar so the
human can edit it at the plan gate and the pipeline can parse it back.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from harness.errors import MalformedArtifactError

_CONCEPT_HEADING = re.compile(r"^### (?P<id>[\w-]+) — (?P<title>.+)$")
_META_LINE = re.compile(r"^- (?P<key>topics|entry): (?P<value>.+)$")
_EDGE_LINE = re.compile(
    r"^- (?P<from>[\w-]+) -> (?P<to>[\w-]+) \| angle: (?P<angle>.+?)"
    r" \| rationale: (?P<rationale>.+)$"
)


@dataclass(frozen=True)
class PieceConcept:
    """One planned Piece — title + premise + Topic tags, no prose yet.

    Attributes:
        id: The Piece id the whole run will use for this concept.
        title: The working title.
        premise: What the Piece will argue/reveal, concretely.
        topic_ids: The Topics the Piece will be tagged with.
        entry_worthy: True if the plan marks it able to open cold (J3).
    """

    id: str
    title: str
    premise: str
    topic_ids: Sequence[str] = field(default_factory=tuple)
    entry_worthy: bool = False

    def __post_init__(self) -> None:
        """Normalize Topic tags to a tuple."""
        object.__setattr__(self, "topic_ids", tuple(self.topic_ids))


@dataclass(frozen=True)
class PlannedConnection:
    """One planned Connection of the skeleton, with its intended hook angle.

    Attributes:
        from_piece_id: The origin concept.
        to_piece_id: The destination concept.
        hook_angle: The curiosity gap the Weaver should realize.
        rationale: The real relationship that earns the jump.
    """

    from_piece_id: str
    to_piece_id: str
    hook_angle: str
    rationale: str


@dataclass(frozen=True)
class ConstellationPlan:
    """The full plan the Architect emits and the human approves.

    Attributes:
        concepts: Every planned Piece concept.
        connections: The full Connection skeleton.
    """

    concepts: Sequence[PieceConcept] = field(default_factory=tuple)
    connections: Sequence[PlannedConnection] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Normalize sequences to tuples."""
        object.__setattr__(self, "concepts", tuple(self.concepts))
        object.__setattr__(self, "connections", tuple(self.connections))

    def concept_ids(self) -> tuple[str, ...]:
        """Return the planned Piece ids in plan order.

        Returns:
            The ids.
        """
        return tuple(concept.id for concept in self.concepts)


def render_plan(plan: ConstellationPlan) -> str:
    """Serialize a plan to its ``plan.md`` text.

    Args:
        plan: The plan to serialize.

    Returns:
        The deliverable text.
    """
    lines: list[str] = ["## Pieces", ""]
    for concept in plan.concepts:
        lines.append(f"### {concept.id} — {concept.title}")
        lines.append(f"- topics: {', '.join(concept.topic_ids)}")
        lines.append(f"- entry: {'yes' if concept.entry_worthy else 'no'}")
        lines.extend(["", concept.premise, ""])
    lines.extend(["## Connections", ""])
    for edge in plan.connections:
        lines.append(
            f"- {edge.from_piece_id} -> {edge.to_piece_id} | angle: {edge.hook_angle}"
            f" | rationale: {edge.rationale}"
        )
    return "\n".join(lines).rstrip() + "\n"


def parse_plan(text: str) -> ConstellationPlan:
    """Parse ``plan.md`` text back into a plan.

    Args:
        text: The deliverable text (possibly human-edited).

    Returns:
        The parsed plan.

    Raises:
        MalformedArtifactError: If no Piece concepts could be parsed.
    """
    concepts: list[PieceConcept] = []
    connections: list[PlannedConnection] = []
    current: dict[str, object] | None = None
    premise_lines: list[str] = []

    def flush() -> None:
        """Finalize the concept currently being accumulated."""
        if current is not None:
            concepts.append(
                PieceConcept(
                    id=str(current["id"]),
                    title=str(current["title"]),
                    premise=" ".join(premise_lines).strip(),
                    topic_ids=tuple(current.get("topics", ())),  # type: ignore[arg-type]
                    entry_worthy=bool(current.get("entry", False)),
                )
            )

    for raw in text.splitlines():
        line = raw.strip()
        heading = _CONCEPT_HEADING.match(line)
        if heading:
            flush()
            current = {"id": heading.group("id"), "title": heading.group("title").strip()}
            premise_lines = []
            continue
        if line.startswith("## "):
            flush()
            current = None
            premise_lines = []
            continue
        edge = _EDGE_LINE.match(line)
        if edge:
            connections.append(
                PlannedConnection(
                    from_piece_id=edge.group("from"),
                    to_piece_id=edge.group("to"),
                    hook_angle=edge.group("angle").strip(),
                    rationale=edge.group("rationale").strip(),
                )
            )
            continue
        if current is not None:
            meta = _META_LINE.match(line)
            if meta and meta.group("key") == "topics":
                current["topics"] = tuple(
                    topic.strip() for topic in meta.group("value").split(",") if topic.strip()
                )
            elif meta and meta.group("key") == "entry":
                current["entry"] = meta.group("value").strip().lower() in {"yes", "true"}
            elif line:
                premise_lines.append(line)
    flush()

    if not concepts:
        raise MalformedArtifactError("plan.md contains no Piece concepts")
    return ConstellationPlan(concepts=tuple(concepts), connections=tuple(connections))

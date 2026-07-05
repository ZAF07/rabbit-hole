"""Serialize/parse a Piece deliverable (``draft.md`` / ``piece.md``).

The grammar is strict but natural markdown, so the human can edit the
working copy at the Piece gate and the pipeline can parse it back:

- front matter carries id/title/teaser/read_time_min/topics;
- ``#``-headings become heading blocks;
- ``>`` blocks become pull-quotes (a final ``> — name`` line attributes);
- ``::stat <value> | <label>`` lines become stat-callouts;
- everything else groups into paragraph blocks.
"""

import re

from content_graph.domain.blocks import BlockKind, ContentBlock
from harness.domain.artifacts import PieceArtifact
from harness.domain.frontmatter import render_frontmatter, split_frontmatter
from harness.errors import MalformedArtifactError

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_STAT = re.compile(r"^::stat\s+(?P<value>.+?)\s*\|\s*(?P<label>.+)$")
_ATTRIBUTION = re.compile(r"^—\s*(.+)$")


def render_piece(piece: PieceArtifact) -> str:
    """Serialize a Piece artifact to deliverable text.

    Args:
        piece: The artifact to serialize.

    Returns:
        The deliverable text.
    """
    fields: dict[str, str | int | bool | list[str]] = {
        "id": piece.id,
        "title": piece.title,
        "teaser": piece.teaser,
        "read_time_min": piece.read_time_min,
        "topics": ", ".join(piece.topic_ids),
    }
    chunks: list[str] = []
    for block in piece.blocks:
        if block.kind is BlockKind.HEADING:
            level = block.payload.get("level", 2)
            depth = level if isinstance(level, int) and 1 <= level <= 6 else 2
            chunks.append(f"{'#' * depth} {block.payload.get('text', '')}")
        elif block.kind is BlockKind.PULL_QUOTE:
            text = str(block.payload.get("text", ""))
            quote_lines = [f"> {line}" for line in text.splitlines()]
            attribution = block.payload.get("attribution")
            if isinstance(attribution, str) and attribution.strip():
                quote_lines.append(f"> — {attribution}")
            chunks.append("\n".join(quote_lines))
        elif block.kind is BlockKind.STAT_CALLOUT:
            chunks.append(
                f"::stat {block.payload.get('value', '')} | {block.payload.get('label', '')}"
            )
        else:
            chunks.append(str(block.payload.get("text", "")))
    return render_frontmatter(fields, "\n\n".join(chunks))


def _flush_paragraph(lines: list[str], blocks: list[ContentBlock]) -> None:
    """Emit accumulated paragraph lines as one paragraph block.

    Args:
        lines: The pending lines; cleared in place.
        blocks: The block list under construction.
    """
    if lines:
        blocks.append(
            ContentBlock(kind=BlockKind.PARAGRAPH, payload={"text": " ".join(lines).strip()})
        )
        lines.clear()


def _flush_quote(lines: list[str], blocks: list[ContentBlock]) -> None:
    """Emit accumulated quote lines as one pull-quote block.

    Args:
        lines: The pending ``>``-stripped lines; cleared in place.
        blocks: The block list under construction.
    """
    if not lines:
        return
    attribution: str | None = None
    matched = _ATTRIBUTION.match(lines[-1])
    if matched and len(lines) > 1:
        attribution = matched.group(1).strip()
        lines = lines[:-1]
    payload: dict[str, object] = {"text": "\n".join(lines).strip()}
    if attribution:
        payload["attribution"] = attribution
    blocks.append(ContentBlock(kind=BlockKind.PULL_QUOTE, payload=payload))


def parse_piece(text: str) -> PieceArtifact:
    """Parse deliverable text back into a Piece artifact.

    Args:
        text: The deliverable text (possibly human-edited).

    Returns:
        The parsed artifact.

    Raises:
        MalformedArtifactError: If the front matter lacks an id.
    """
    fields, body = split_frontmatter(text)
    piece_id = fields.get("id")
    if not isinstance(piece_id, str) or not piece_id.strip():
        raise MalformedArtifactError("piece deliverable has no id in front matter")

    blocks: list[ContentBlock] = []
    paragraph: list[str] = []
    quote: list[str] = []
    for raw in body.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith(">"):
            _flush_paragraph(paragraph, blocks)
            quote.append(stripped.lstrip("> ").strip())
            continue
        _flush_quote(quote, blocks)
        quote = []
        if not stripped:
            _flush_paragraph(paragraph, blocks)
            continue
        heading = _HEADING.match(stripped)
        if heading:
            _flush_paragraph(paragraph, blocks)
            blocks.append(
                ContentBlock(
                    kind=BlockKind.HEADING,
                    payload={"text": heading.group(2).strip(), "level": len(heading.group(1))},
                )
            )
            continue
        stat = _STAT.match(stripped)
        if stat:
            _flush_paragraph(paragraph, blocks)
            blocks.append(
                ContentBlock(
                    kind=BlockKind.STAT_CALLOUT,
                    payload={
                        "value": stat.group("value").strip(),
                        "label": stat.group("label").strip(),
                    },
                )
            )
            continue
        paragraph.append(stripped)
    _flush_paragraph(paragraph, blocks)
    _flush_quote(quote, blocks)

    raw_read_time = fields.get("read_time_min", "0")
    read_time = (
        int(raw_read_time) if isinstance(raw_read_time, str) and raw_read_time.isdigit() else 0
    )
    topics_field = fields.get("topics", "")
    topics = (
        tuple(topic.strip() for topic in topics_field.split(",") if topic.strip())
        if isinstance(topics_field, str)
        else tuple(topics_field)
    )
    title = fields.get("title", "")
    teaser = fields.get("teaser", "")
    return PieceArtifact(
        id=piece_id.strip(),
        title=title if isinstance(title, str) else "",
        teaser=teaser if isinstance(teaser, str) else "",
        read_time_min=read_time,
        topic_ids=topics,
        blocks=tuple(blocks),
    )

"""The publish gate — re-wire, re-QA, and atomically write the approved subset.

Publishing is never a bare insert (ADR 0012): the human may have rejected
Pieces, so the Weaver and Reviewer re-run over the survivors, a survivor
that cannot be made contract-valid is flagged back to the human, and only
the re-validated set is written — all validation happens before any write.
"""

import json

from content_graph.domain.connection import Connection
from content_graph.domain.piece import Piece
from content_graph.domain.topic import Topic
from harness.domain.grounding_io import ledger_from_json
from harness.domain.piece_io import parse_piece
from harness.domain.qa_report import QAReport, render_qa_report
from harness.domain.wiring import parse_connections
from harness.errors import PublishIntegrityError
from harness.guardrails.constellation import evaluate_constellation
from harness.pipeline.context import RunContext
from harness.pipeline.stages import (
    assemble_constellation,
    grounding_path,
    piece_path,
    run_stage_wire,
)

PUBLISH_CONNECTIONS = "publish/connections.md"
PUBLISH_QA = "publish/qa.md"
PUBLISH_RECEIPT = "publish/published.json"
PUBLISH_FLAGS = "publish/flags.md"


def run_stage_rewire(ctx: RunContext, survivors: frozenset[str]) -> None:
    """The Weaver's second mode — re-wire the approved survivors.

    Args:
        ctx: The run context.
        survivors: The human-approved Piece ids.
    """
    run_stage_wire(ctx, output_path=PUBLISH_CONNECTIONS, survivors=survivors)


def run_stage_reqa(
    ctx: RunContext, survivors: frozenset[str]
) -> tuple[frozenset[str], frozenset[str]]:
    """The Reviewer's second mode — re-QA the survivors, flagging the unfixable.

    A survivor implicated in a graph-integrity failure is flagged back to
    the human and removed; the remainder is re-wired and re-QA'd once more.

    Args:
        ctx: The run context.
        survivors: The human-approved Piece ids.

    Returns:
        (the re-validated survivor set, the flagged Piece ids).

    Raises:
        PublishIntegrityError: If no contract-valid survivor set exists
            even after flagging.
    """
    stage = ctx.manifest.stage("reqa")
    ctx.workspace.require(stage.name, *stage.prerequisites)
    validated = frozenset(survivors)
    flagged: set[str] = set()
    for _ in range(2):
        constellation = assemble_constellation(
            ctx, connections_source=PUBLISH_CONNECTIONS, survivors=validated
        )
        report = evaluate_constellation(constellation, ctx.specs.banned_phrases())
        if report.passed:
            ctx.workspace.write(PUBLISH_QA, render_qa_report(QAReport(tier1=report)))
            _write_flags(ctx, flagged)
            return validated, frozenset(flagged)
        implicated = {
            violation.subject for violation in report.violations if violation.subject in validated
        }
        if not implicated:
            break
        flagged.update(implicated)
        validated = validated - implicated
        if len(validated) < 2:
            break
        ctx.workspace.path(PUBLISH_CONNECTIONS).unlink(missing_ok=True)
        run_stage_rewire(ctx, validated)
    raise PublishIntegrityError(
        "no contract-valid survivor set could be published; flagged back to the human: "
        + ", ".join(sorted(flagged or survivors))
    )


def _write_flags(ctx: RunContext, flagged: set[str]) -> None:
    """Record the Pieces flagged back to the human during re-QA.

    Args:
        ctx: The run context.
        flagged: The flagged Piece ids.
    """
    if flagged:
        lines = ["# Flagged back to the human — re-wire, hold, or cut", ""]
        lines.extend(f"- {piece_id}" for piece_id in sorted(flagged))
        ctx.workspace.write(PUBLISH_FLAGS, "\n".join(lines) + "\n")


def _title_from_tag(tag: str) -> str:
    """Derive a display title for a Topic the graph does not know yet.

    Args:
        tag: The Topic id/slug.

    Returns:
        A humanized title.
    """
    return tag.replace("-", " ").title()


def run_stage_write(ctx: RunContext, survivors: frozenset[str]) -> tuple[str, ...]:
    """Atomically write the re-validated survivor set through the write surface.

    Everything is parsed and validated before the first upsert, so either
    the full set lands or nothing does. Only Pieces, Connections, and Topic
    tags cross the boundary (ADR 0006).

    Args:
        ctx: The run context.
        survivors: The re-validated survivor ids.

    Returns:
        The published Piece ids.

    Raises:
        PublishIntegrityError: If a survivor's deliverables are missing or
            invalid at write time.
    """
    stage = ctx.manifest.stage("write")
    ctx.workspace.require(stage.name, *stage.prerequisites)
    try:
        artifacts = [
            parse_piece(ctx.workspace.read(piece_path(piece_id))) for piece_id in sorted(survivors)
        ]
        edges = [
            edge
            for edge in parse_connections(ctx.workspace.read(PUBLISH_CONNECTIONS))
            if edge.from_piece_id in survivors and edge.to_piece_id in survivors
        ]
        for piece_id in sorted(survivors):
            ledger_from_json(ctx.workspace.read(grounding_path(piece_id)))
        pieces = [
            Piece(
                id=artifact.id,
                title=artifact.title,
                teaser=artifact.teaser,
                read_time_min=artifact.read_time_min,
                blocks=tuple(artifact.blocks),
                topic_ids=tuple(artifact.topic_ids),
                run_id=ctx.run_id,
            )
            for artifact in artifacts
        ]
        connections = [
            Connection(
                from_piece_id=edge.from_piece_id, to_piece_id=edge.to_piece_id, hook=edge.hook
            )
            for edge in edges
        ]
    except Exception as error:
        raise PublishIntegrityError(f"survivor set failed pre-write validation: {error}") from error

    topic_ids = sorted({tag for piece in pieces for tag in piece.topic_ids})
    for tag in topic_ids:
        if ctx.repo.get_topic(tag) is None:
            ctx.repo.upsert_topic(Topic(id=tag, slug=tag, title=_title_from_tag(tag)))
    for piece in pieces:
        ctx.repo.upsert_piece(piece)
    for connection in connections:
        ctx.repo.upsert_connection(connection)

    receipt = {
        "run_id": ctx.run_id,
        "pieces": [piece.id for piece in pieces],
        "connections": [[edge.from_piece_id, edge.to_piece_id] for edge in edges],
        "topics": topic_ids,
    }
    ctx.workspace.write(PUBLISH_RECEIPT, json.dumps(receipt, indent=2) + "\n")
    return tuple(piece.id for piece in pieces)

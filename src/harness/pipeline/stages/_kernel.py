"""Cross-agent helpers shared by the stage modules and the publish gate.

The workspace path map, the per-Piece fan-out bound, the Brief/plan loaders,
and the constellation assembler are used by more than one agent module (and by
:mod:`harness.pipeline.publish`), so they live here rather than inside any one
agent. Agent-local helpers stay with their agent.
"""

from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor

from harness.domain.artifacts import ConstellationArtifact
from harness.domain.brief import ThemeBrief, parse_brief
from harness.domain.grounding_io import ledger_from_json
from harness.domain.piece_io import parse_piece
from harness.domain.plan import ConstellationPlan, parse_plan
from harness.domain.wiring import parse_connections
from harness.manifest import StageSpec
from harness.pipeline.context import RunContext

GOAL = "goal.md"
PLAN = "plan.md"
CONNECTIONS = "connections.md"
QA = "qa.md"


def sources_path(piece_id: str) -> str:
    """Workspace path of a Piece's claim pack.

    Args:
        piece_id: The Piece.

    Returns:
        The relative path.
    """
    return f"pieces/{piece_id}/sources.md"


def grounding_path(piece_id: str) -> str:
    """Workspace path of a Piece's grounding ledger.

    Args:
        piece_id: The Piece.

    Returns:
        The relative path.
    """
    return f"pieces/{piece_id}/grounding.json"


def draft_path(piece_id: str) -> str:
    """Workspace path of a Piece's draft.

    Args:
        piece_id: The Piece.

    Returns:
        The relative path.
    """
    return f"pieces/{piece_id}/draft.md"


def piece_path(piece_id: str) -> str:
    """Workspace path of a Piece's final deliverable.

    Args:
        piece_id: The Piece.

    Returns:
        The relative path.
    """
    return f"pieces/{piece_id}/piece.md"


def failure_path(piece_id: str) -> str:
    """Workspace path of a Piece's failure marker.

    A fan-out stage records a Piece that failed its bar here (its failure
    code) rather than aborting the whole run, so the human sees every failed
    Piece in one review pass.

    Args:
        piece_id: The Piece.

    Returns:
        The relative path.
    """
    return f"pieces/{piece_id}/failure.md"


def has_failed(ctx: RunContext, piece_id: str) -> bool:
    """Whether a Piece carries a recorded failure marker.

    Args:
        ctx: The run context.
        piece_id: The Piece.

    Returns:
        True if the Piece failed a bar in an earlier (or this) stage.
    """
    return ctx.workspace.exists(failure_path(piece_id))


def _record_failure(ctx: RunContext, piece_id: str, code: str, message: str) -> None:
    """Persist a Piece's failure code + message as its review marker.

    Args:
        ctx: The run context.
        piece_id: The failed Piece.
        code: The failure code (the exception class name).
        message: The failure detail.
    """
    ctx.workspace.write(
        failure_path(piece_id),
        f"# Piece failed its bar\n\ncode: {code}\n\n{message}\n",
    )


def _fan_out[T](ctx: RunContext, items: Sequence[T], work: Callable[[T], None]) -> None:
    """Run per-Piece work concurrently under the ``fan_out`` bound (a barrier).

    Every item is processed before returning (a within-stage barrier), so the
    deliverable-on-disk gate and resume idempotence hold exactly as in the
    serial pipeline. ``fan_out == 1`` (or a single item) runs serially.
    ``work`` is expected to collect a Piece's own *bar* failure (writing a
    marker); any exception it does not handle is a genuine bug and is
    re-raised after the barrier.

    Args:
        ctx: The run context.
        items: The per-Piece work items.
        work: The per-item worker.
    """
    workers = max(1, ctx.config.fan_out)
    ordered = list(items)
    if workers == 1 or len(ordered) <= 1:
        for item in ordered:
            work(item)
        return
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, item) for item in ordered]
        for future in futures:
            future.result()


def expanded_prerequisites(stage: StageSpec, piece_ids: Iterable[str]) -> list[str]:
    """Expand a stage's prerequisite templates over the planned Pieces.

    Args:
        stage: The stage spec from the manifest.
        piece_ids: The planned Piece ids to expand ``{piece_id}`` over.

    Returns:
        The concrete workspace-relative paths.
    """
    paths: list[str] = []
    ids = list(piece_ids)
    for template in stage.prerequisites:
        if "{piece_id}" in template:
            paths.extend(stage.expand(template, piece_id) for piece_id in ids)
        else:
            paths.append(template)
    return paths


def load_brief(ctx: RunContext) -> ThemeBrief:
    """Read and validate the run's Theme Brief.

    Args:
        ctx: The run context.

    Returns:
        The parsed Brief.
    """
    return parse_brief(ctx.workspace.read(GOAL))


def load_plan(ctx: RunContext) -> ConstellationPlan:
    """Read the approved plan (the working copy, which the human may have edited).

    Args:
        ctx: The run context.

    Returns:
        The parsed plan.
    """
    return parse_plan(ctx.workspace.read(PLAN))


def voice_name(ctx: RunContext, brief: ThemeBrief) -> str:
    """Resolve the active Voice Profile for the run.

    Args:
        ctx: The run context.
        brief: The run's Brief.

    Returns:
        The profile name.
    """
    return brief.voice or ctx.config.default_voice


def assemble_constellation(
    ctx: RunContext, connections_source: str = CONNECTIONS, survivors: frozenset[str] | None = None
) -> ConstellationArtifact:
    """Build the constellation artifact from the deliverables on disk.

    Args:
        ctx: The run context.
        connections_source: Which connections deliverable to read.
        survivors: When re-QAing, the approved Piece ids; None takes the
            full plan and the Brief's own targets.

    Returns:
        The assembled artifact.
    """
    brief = load_brief(ctx)
    plan = load_plan(ctx)
    concept_ids = [
        concept.id for concept in plan.concepts if survivors is None or concept.id in survivors
    ]
    pieces = tuple(
        parse_piece(ctx.workspace.read(piece_path(piece_id))) for piece_id in concept_ids
    )
    connections = parse_connections(ctx.workspace.read(connections_source))
    ledgers = {
        piece_id: ledger_from_json(ctx.workspace.read(grounding_path(piece_id)))
        for piece_id in concept_ids
    }
    if survivors is None:
        target, topics = brief.piece_count, brief.target_topics
    else:
        target, topics = (len(concept_ids), len(concept_ids)), ()
    return ConstellationArtifact(
        pieces=pieces,
        connections=connections,
        ledgers=ledgers,
        piece_count_target=target,
        target_topic_ids=topics,
    )

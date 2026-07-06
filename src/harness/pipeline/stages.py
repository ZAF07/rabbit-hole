"""The seven pipeline stages, each a bounded loop behind a file gate.

Every stage: refuses to start without its manifest prerequisites on disk,
skips work whose deliverable already exists (resume idempotence), does its
job through the ports, and writes its deliverable — which is the next
stage's gate.
"""

import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock as _Lock

from content_graph.domain.read_models import PieceSummary
from harness.domain.artifacts import ConstellationArtifact, PieceArtifact, WiredConnection
from harness.domain.brief import ThemeBrief, find_placeholders, parse_brief
from harness.domain.grounding import (
    ClaimRecord,
    ClaimStatus,
    GroundingLedger,
    RefutationVerdict,
    SourceRecord,
    SourceTier,
)
from harness.domain.grounding_io import ledger_from_json, ledger_to_json
from harness.domain.piece_io import parse_piece, render_piece
from harness.domain.plan import (
    ConstellationPlan,
    PieceConcept,
    PlannedConnection,
    parse_plan,
    render_plan,
)
from harness.domain.qa_report import QAReport, parse_qa_outcome, render_qa_report
from harness.domain.wiring import parse_connections, render_connections
from harness.errors import (
    ContractViolationError,
    GroundingDriftError,
    LLMResponseError,
    QABudgetExceededError,
    ThinSourcePackError,
)
from harness.guardrails.connection import evaluate_connections
from harness.guardrails.constellation import Tier2Judgement, evaluate_constellation
from harness.guardrails.piece import JUDGED_PIECE_CHECKS, evaluate_piece
from harness.guardrails.violations import Violation
from harness.manifest import StageSpec
from harness.pipeline.context import RunContext
from harness.pipeline.decode import (
    decode_object,
    decode_object_list,
    decode_piece_payload,
    decode_plan,
)
from harness.ports.llm import LLMRequest, ToolSpec
from harness.ports.web_source import FetchedPage

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


def run_stage_gate0(ctx: RunContext) -> str | None:
    """Stage 0 — refuse to start unless DNA + a placeholder-free Brief exist.

    Args:
        ctx: The run context.

    Returns:
        None if the gate passes, otherwise the concrete failure reason.
    """
    try:
        dna = ctx.specs.dna_text()
    except OSError:
        return "Editorial DNA (harness/editorial/dna.md) is missing"
    if not dna.strip():
        return "Editorial DNA is empty"
    if not ctx.workspace.exists(GOAL):
        return "Theme Brief (goal.md) is missing from the run workspace"
    raw = ctx.workspace.read(GOAL)
    placeholders = find_placeholders(raw)
    if placeholders:
        return f"Theme Brief has unfilled placeholders: {', '.join(placeholders)}"
    try:
        parse_brief(raw)
    except Exception as error:  # noqa: BLE001
        return f"Theme Brief is invalid: {error}"
    return None


def run_stage_plan(ctx: RunContext) -> None:
    """Stage 1 — the Architect designs the whole constellation before any prose.

    Args:
        ctx: The run context.
    """
    stage = ctx.manifest.stage("plan")
    ctx.workspace.require(stage.name, *stage.prerequisites)
    if ctx.workspace.exists(PLAN):
        return
    brief = load_brief(ctx)
    existing = ctx.repo.list_piece_summaries()
    request = LLMRequest(
        purpose="architect.plan",
        instructions="\n\n---\n\n".join(
            (
                ctx.specs.dna_text(),
                ctx.specs.guardrail_text("connection"),
                ctx.specs.guardrail_text("constellation"),
                ctx.specs.taxonomy_text(),
            )
        ),
        payload={
            "through_line": brief.through_line,
            "target_topics": list(brief.target_topics),
            "piece_count": list(brief.piece_count),
            "must_include": list(brief.must_include),
            "entry_hints": list(brief.entry_hints),
            "must_avoid": list(brief.must_avoid),
            "notes": brief.notes,
            "existing_pieces": [
                {"id": summary.id, "title": summary.title, "teaser": summary.teaser}
                for summary in existing
            ],
        },
    )
    plan = decode_plan(ctx.llm.complete(request))
    _assert_no_duplicates(plan, existing)
    _assert_plan_sound(plan, brief)
    ctx.workspace.write(PLAN, render_plan(plan))


def _assert_no_duplicates(plan: ConstellationPlan, existing: Sequence[PieceSummary]) -> None:
    """Refuse a plan that duplicates a Piece already in the Content Graph.

    The Architect reads the published graph to bridge to it, not to
    re-plan it; the LLM is instructed to avoid duplicates and this backstop
    makes the guarantee hard.

    Args:
        plan: The proposed plan.
        existing: The published Pieces the Architect was shown.

    Raises:
        ContractViolationError: If a proposed concept collides with an
            existing Piece by id or normalized title.
    """
    existing_ids = {summary.id for summary in existing}
    existing_titles = {summary.title.strip().casefold() for summary in existing}
    for concept in plan.concepts:
        if concept.id in existing_ids:
            raise ContractViolationError(
                f"plan proposes Piece id {concept.id!r} which already exists in the Content Graph"
            )
        if concept.title.strip().casefold() in existing_titles:
            raise ContractViolationError(
                f"plan duplicates the existing Piece titled {concept.title!r}"
            )


def _assert_plan_sound(plan: ConstellationPlan, brief: ThemeBrief) -> None:
    """Check the plan's structural invariants hold by construction.

    Args:
        plan: The proposed plan.
        brief: The run's Brief.

    Raises:
        ContractViolationError: If the planned skeleton could not satisfy
            the outcome contract (dead ends, missing cross-Topic edges,
            disconnection, count/coverage misses, or duplicate ids).
    """
    ids = [concept.id for concept in plan.concepts]
    if len(set(ids)) != len(ids):
        raise ContractViolationError("plan proposes duplicate Piece ids")
    planned = ConstellationArtifact(
        pieces=tuple(
            PieceArtifact(
                id=concept.id,
                title=concept.title,
                teaser=concept.premise or concept.title,
                read_time_min=5,
                topic_ids=concept.topic_ids,
            )
            for concept in plan.concepts
        ),
        connections=tuple(
            WiredConnection(
                from_piece_id=edge.from_piece_id,
                to_piece_id=edge.to_piece_id,
                hook=edge.hook_angle,
                rationale=edge.rationale,
            )
            for edge in plan.connections
        ),
        piece_count_target=brief.piece_count,
        target_topic_ids=brief.target_topics,
    )
    report = evaluate_constellation(planned, banned_phrases=())
    structural = [
        violation
        for violation in report.violations
        if violation.code in {"I1", "I3", "I4", "I5", "I6", "I7"}
        and "guardrails" not in violation.message
    ]
    if structural:
        summary = "; ".join(f"{v.code} {v.subject}: {v.message}" for v in structural[:5])
        raise ContractViolationError(f"planned skeleton is structurally unsound: {summary}")
    if not any(concept.entry_worthy for concept in plan.concepts):
        raise ContractViolationError("plan marks no entry-worthy node (J3)")


def _navigate_sources(
    ctx: RunContext, concept: PieceConcept, sourcing_spec: str, roots: Sequence[str]
) -> dict[str, FetchedPage]:
    """Navigate cited outlinks toward primary sources via a bounded agent.

    The Researcher agent follows the recalled hub's cited outlinks the way a
    person following footnotes would (its ``fetch`` tool wraps the existing
    ``WebSourcePort.fetch`` — no ``search``, ADR 0011). The agent carries
    ``sourcing.md`` (incl. its Navigation section) as its authored
    instructions; ``step_limit`` bounds the walk. Every page the agent reaches
    is captured here as a side effect, so the deterministic assess /
    corroborate / refute checks downstream stay the arbiter of admission.

    Args:
        ctx: The run context.
        concept: The planned Piece being sourced.
        sourcing_spec: The sourcing guardrail text (the agent's instructions).
        roots: The recall-proposed candidate hub URLs to start from.

    Returns:
        URL → fetched page, for every page the agent reached.
    """
    reached: dict[str, FetchedPage] = {}

    def fetch_run(args: Mapping[str, object]) -> str:
        url = str(args["url"])
        page = reached.get(url)
        if page is None and url not in reached:
            page = ctx.web.fetch(url)
            if page is not None:
                reached[url] = page
        if page is None:
            return json.dumps({"url": url, "error": "unreachable"})
        return json.dumps({"url": url, "content": page.content, "outlinks": list(page.outlinks)})

    fetch_tool = ToolSpec(
        name="fetch",
        description=(
            "Fetch one URL's readable content and its cited outbound links. "
            "Follow citation/footnote outlinks toward the primary tier; there "
            "is no search — navigate from the given candidate URLs."
        ),
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        run=fetch_run,
    )
    ctx.llm.run_agent(
        LLMRequest(
            purpose="researcher.navigate",
            instructions=sourcing_spec,
            payload={
                "piece_id": concept.id,
                "title": concept.title,
                "premise": concept.premise,
                "candidate_urls": list(roots),
            },
        ),
        [fetch_tool],
        step_limit=ctx.config.agent_step_limit,
    )
    return reached


def _snapshot_pages(ctx: RunContext, piece_id: str, pages: dict[str, FetchedPage]) -> None:
    """Snapshot fetched source content into the run workspace.

    Args:
        ctx: The run context.
        piece_id: The Piece the sources back.
        pages: The fetched pages.
    """
    for index, (url, page) in enumerate(sorted(pages.items()), start=1):
        safe = "".join(char if char.isalnum() else "-" for char in url).strip("-")[:80]
        ctx.workspace.write(
            f"pieces/{piece_id}/snapshots/{index:02d}-{safe}.txt",
            f"url: {url}\nfetched_at: {page.fetched_at}\n\n{page.content}\n",
        )


def _best_tier(sources: tuple[SourceRecord, ...]) -> SourceTier:
    """The strongest tier among a claim's sources.

    Args:
        sources: The claim's backing sources.

    Returns:
        The best tier; TERTIARY when there are no sources.
    """
    order = (SourceTier.PRIMARY, SourceTier.SECONDARY, SourceTier.TERTIARY)
    for tier in order:
        if any(source.tier is tier for source in sources):
            return tier
    return SourceTier.TERTIARY


def admit_claim(sources: tuple[SourceRecord, ...], load_bearing: bool) -> tuple[ClaimStatus, bool]:
    """Apply the corroboration bar (guardrails/sourcing.md) to one claim.

    A primary source suffices alone; secondary/tertiary needs at least two
    independent origins; an internal-only or uncorroborated claim is dropped
    by default and flagged only if load-bearing.

    Args:
        sources: The claim's vetted backing sources.
        load_bearing: Whether the Piece's premise depends on the claim.

    Returns:
        (admission status, whether the claim is internal-only).
    """
    internal_only = not sources
    if any(source.tier is SourceTier.PRIMARY for source in sources):
        return ClaimStatus.VERIFIED, internal_only
    independent = {source.independence_key() for source in sources}
    if len(independent) >= 2:
        return ClaimStatus.VERIFIED, internal_only
    status = ClaimStatus.FLAGGED if load_bearing else ClaimStatus.DROPPED
    return status, internal_only


def _render_claim_pack(piece_id: str, ledger: GroundingLedger) -> str:
    """Render the human-readable claim pack (``sources.md``).

    Args:
        piece_id: The Piece.
        ledger: The completed ledger.

    Returns:
        The deliverable text.
    """
    lines = [f"# Claim pack — {piece_id}", "", "## Verified claims", ""]
    for claim in ledger.verified_claims():
        lines.append(f"- [{claim.id}] {claim.text}")
        lines.extend(
            f"  - source: {source.citation} ({source.tier}) — {source.excerpt}"
            for source in claim.sources
        )
    rest = [claim for claim in ledger.claims if claim.status is not ClaimStatus.VERIFIED]
    if rest:
        lines.extend(["", "## Dropped / flagged", ""])
        lines.extend(f"- [{claim.id}] {claim.status} — {claim.text}" for claim in rest)
    return "\n".join(lines).rstrip() + "\n"


def run_stage_source(ctx: RunContext) -> None:
    """Stage 2 — the closed-book Researcher, per planned Piece (fanned out).

    Harvest (recall proposes claims + candidate URLs) → agentic navigation →
    Vet/assess each page → Corroborate against the bar → Refute survivors.
    Pieces are researched concurrently under the ``fan_out`` bound; the stage
    finishes every Piece before surfacing any thin-pack failure, so the human
    sees all the run's research problems in one pass rather than one at a
    time. A thin Piece dies at research, not in prose: unlike an Edit-bar
    failure (which has a best-effort draft to route into the piece gate), a
    thin Piece has no vetted claim pack to draft from, so research failures
    are fatal to the run — reported together, not routed onward.

    Args:
        ctx: The run context.

    Raises:
        ThinSourcePackError: If any Piece's verified claims fall below the bar
            (reported for every thin Piece at once).
    """
    stage = ctx.manifest.stage("source")
    ctx.workspace.require(stage.name, *stage.prerequisites)
    plan = load_plan(ctx)
    sourcing_spec = ctx.specs.guardrail_text("sourcing")
    thin: dict[str, int] = {}
    lock = _Lock()

    def work(concept: PieceConcept) -> None:
        if ctx.workspace.exists(sources_path(concept.id)) and ctx.workspace.exists(
            grounding_path(concept.id)
        ):
            return
        ledger = _research_piece(ctx, concept, sourcing_spec)
        verified = ledger.verified_claims()
        if len(verified) < ctx.config.min_verified_claims:
            with lock:
                thin[concept.id] = len(verified)
            return
        ctx.workspace.write(grounding_path(concept.id), ledger_to_json(ledger))
        ctx.workspace.write(sources_path(concept.id), _render_claim_pack(concept.id, ledger))

    _fan_out(ctx, plan.concepts, work)
    if thin:
        summary = "; ".join(
            f"{piece_id} ({count} verified)" for piece_id, count in sorted(thin.items())
        )
        raise ThinSourcePackError(
            f"{len(thin)} Piece(s) each dies at research, not in prose: {summary} "
            f"(needs {ctx.config.min_verified_claims} verified claim(s) each)"
        )


def _research_piece(ctx: RunContext, concept: PieceConcept, sourcing_spec: str) -> GroundingLedger:
    """Run the 2a–2d sub-pipeline for one Piece concept.

    Args:
        ctx: The run context.
        concept: The planned Piece.
        sourcing_spec: The sourcing guardrail text.

    Returns:
        The completed grounding ledger.
    """
    harvest = decode_object_list(
        ctx.llm.complete(
            LLMRequest(
                purpose="researcher.harvest",
                instructions=sourcing_spec,
                payload={
                    "piece_id": concept.id,
                    "title": concept.title,
                    "premise": concept.premise,
                },
            )
        ),
        key="claims",
        purpose="researcher.harvest",
    )
    candidate_urls = [
        str(url) for claim in harvest for url in claim.get("candidate_urls", []) or []
    ]
    pages = _navigate_sources(ctx, concept, sourcing_spec, candidate_urls)
    _snapshot_pages(ctx, concept.id, pages)

    support: dict[str, list[SourceRecord]] = {str(claim["id"]): [] for claim in harvest}
    for url in sorted(pages):
        page = pages[url]
        assessment = decode_object(
            ctx.llm.complete(
                LLMRequest(
                    purpose="researcher.assess",
                    instructions=sourcing_spec,
                    payload={
                        "url": url,
                        "content": page.content,
                        "claims": [
                            {"id": str(claim["id"]), "text": str(claim["text"])}
                            for claim in harvest
                        ],
                    },
                )
            ),
            purpose="researcher.assess",
        )
        try:
            tier = SourceTier(str(assessment["tier"]))
        except (KeyError, ValueError) as error:
            raise LLMResponseError(f"researcher.assess: bad tier: {error}") from error
        for supported in assessment.get("supports", []):
            claim_id = str(supported.get("claim_id", ""))
            if claim_id in support:
                support[claim_id].append(
                    SourceRecord(
                        citation=url,
                        tier=tier,
                        credibility=str(assessment.get("credibility", "")),
                        excerpt=str(supported.get("excerpt", "")),
                        retrieved_at=page.fetched_at,
                        origin_key=str(assessment.get("origin_key", "")) or url,
                    )
                )

    claims: list[ClaimRecord] = []
    for raw in harvest:
        claim_id = str(raw["id"])
        text = str(raw["text"])
        load_bearing = bool(raw.get("load_bearing", False))
        sources = tuple(support[claim_id])
        status, internal_only = admit_claim(sources, load_bearing)
        refutation: RefutationVerdict | None = None
        if status is ClaimStatus.VERIFIED:
            verdict = decode_object(
                ctx.llm.complete(
                    LLMRequest(
                        purpose="researcher.refute",
                        instructions=sourcing_spec,
                        payload={
                            "claim": text,
                            "sources": [source.citation for source in sources],
                        },
                    )
                ),
                purpose="researcher.refute",
            )
            if str(verdict.get("verdict", "")) == "refuted":
                status = ClaimStatus.DROPPED
                refutation = RefutationVerdict.REFUTED
            else:
                refutation = RefutationVerdict.SURVIVED
        claims.append(
            ClaimRecord(
                id=claim_id,
                text=text,
                tier=_best_tier(sources),
                status=status,
                sources=sources,
                refutation=refutation,
                load_bearing=load_bearing,
                internal_only=internal_only,
            )
        )
    return GroundingLedger(piece_id=concept.id, claims=tuple(claims))


def run_stage_draft(ctx: RunContext) -> None:
    """Stage 3 — the closed-book Writer, per Piece.

    The Writer's input is the vetted claim pack only; the draft is emitted
    as ordered Content Blocks in the active Voice Profile.

    Args:
        ctx: The run context.
    """
    stage = ctx.manifest.stage("draft")
    brief = load_brief(ctx)
    plan = load_plan(ctx)
    voice = ctx.specs.voice_text(voice_name(ctx, brief))
    dna = ctx.specs.dna_text()

    def work(concept: PieceConcept) -> None:
        if ctx.workspace.exists(draft_path(concept.id)):
            return
        ctx.workspace.require(
            stage.name, *(stage.expand(path, concept.id) for path in stage.prerequisites)
        )
        ledger = ledger_from_json(ctx.workspace.read(grounding_path(concept.id)))
        artifact = decode_piece_payload(
            ctx.llm.complete(
                LLMRequest(
                    purpose="writer.draft",
                    instructions=f"{dna}\n\n---\n\n{voice}",
                    payload={
                        "piece_id": concept.id,
                        "title": concept.title,
                        "premise": concept.premise,
                        "topics": list(concept.topic_ids),
                        "claims": [
                            {"id": claim.id, "text": claim.text}
                            for claim in ledger.verified_claims()
                        ],
                    },
                )
            ),
            piece_id=concept.id,
            topic_ids=tuple(concept.topic_ids),
            purpose="writer.draft",
        )
        ctx.workspace.write(draft_path(concept.id), render_piece(artifact))

    _fan_out(ctx, plan.concepts, work)


def run_stage_edit(ctx: RunContext) -> None:
    """Stage 4 — the Editor: anti-slop pass, machine-QA loop, 4.5 grounding check.

    The machine-QA judge combines the mechanical piece evaluator with the
    LLM-judged checks and loops the edit until pass or the QA budget is
    spent; then every factual assertion is mapped back to a verified claim.

    A Piece that fails its bar (the machine-QA loop or the 4.5 grounding
    check) no longer aborts the run: the stage finishes every other Piece,
    persists the Piece's best-effort machine copy (its draft) as ``piece.md``
    plus a failure marker (its failure code), and lets it flow into the piece
    gate as an ordinary review target — the human's edit-approve fix (or a
    rejection) is the same path any Verdict takes.

    Args:
        ctx: The run context.
    """
    stage = ctx.manifest.stage("edit")
    brief = load_brief(ctx)
    plan = load_plan(ctx)
    banned = ctx.specs.banned_phrases()
    voice = ctx.specs.voice_text(voice_name(ctx, brief))
    piece_spec = ctx.specs.guardrail_text("piece")

    def work(concept: PieceConcept) -> None:
        if ctx.workspace.exists(piece_path(concept.id)):
            return
        ctx.workspace.require(
            stage.name, *(stage.expand(path, concept.id) for path in stage.prerequisites)
        )
        draft = parse_piece(ctx.workspace.read(draft_path(concept.id)))
        result = _qa_loop(ctx, draft, banned, voice, piece_spec)
        if result.failure_code is None:
            result = _grounding_check(ctx, concept, result.artifact, banned)
        if result.failure_code is None:
            ctx.workspace.write(piece_path(concept.id), render_piece(result.artifact))
        else:
            ctx.workspace.write(piece_path(concept.id), render_piece(draft))
            _record_failure(ctx, concept.id, result.failure_code, result.detail)

    _fan_out(ctx, plan.concepts, work)


def _judge(
    ctx: RunContext, artifact: PieceArtifact, voice: str, piece_spec: str
) -> list[Violation]:
    """Ask the LLM judge for the non-mechanical piece checks.

    Args:
        ctx: The run context.
        artifact: The Piece under judgment.
        voice: The active Voice Profile text.
        piece_spec: The piece guardrail text.

    Returns:
        The judged violations.
    """
    judged = decode_object_list(
        ctx.llm.complete(
            LLMRequest(
                purpose="editor.judge",
                instructions=f"{piece_spec}\n\n---\n\n{voice}",
                payload={
                    "piece_id": artifact.id,
                    "text": artifact.all_text(),
                    "checks": dict(JUDGED_PIECE_CHECKS),
                },
            )
        ),
        key="violations",
        purpose="editor.judge",
    )
    return [
        Violation(
            code=str(item.get("code", "F1")),
            subject=artifact.id,
            message=str(item.get("message", "")),
            excerpt=str(item["excerpt"]) if item.get("excerpt") else None,
        )
        for item in judged
    ]


def _check_guardrails_tool(
    ctx: RunContext,
    piece_id: str,
    topic_ids: tuple[str, ...],
    banned: tuple[str, ...],
    voice: str,
    piece_spec: str,
) -> ToolSpec:
    """Build the Editor's ``check_guardrails`` tool: evaluate + judge a candidate.

    The tool wraps the deterministic ``evaluate_piece`` **and** the
    non-mechanical LLM voice judge, so the agent sees the checker's verdict
    and revises again within one loop. The judge call carries the authored
    ``piece_spec + voice`` — it is never reduced to voice-blind codes.

    Args:
        ctx: The run context.
        piece_id: The Piece id (candidates cannot rename it).
        topic_ids: The Piece's Topic tags.
        banned: The banned-filler list.
        voice: The active Voice Profile text.
        piece_spec: The piece guardrail text.

    Returns:
        The tool the Editor agent calls to check a revision.
    """
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "teaser": {"type": "string"},
            "read_time_min": {"type": "integer"},
            "blocks": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["blocks"],
    }

    def run(args: Mapping[str, object]) -> str:
        candidate = decode_piece_payload(json.dumps(dict(args)), piece_id, topic_ids, "editor.qa")
        violations = list(evaluate_piece(candidate, banned)) + _judge(
            ctx, candidate, voice, piece_spec
        )
        return json.dumps(
            {
                "violations": [
                    {"code": v.code, "message": v.message, "excerpt": v.excerpt} for v in violations
                ]
            }
        )

    return ToolSpec(
        name="check_guardrails",
        description=(
            "Evaluate the current draft against the piece guardrails and the "
            "voice judge. Pass the candidate's title, teaser, read_time_min, "
            "and blocks; returns the list of remaining violations (empty when "
            "the draft passes)."
        ),
        parameters=schema,
        run=run,
    )


@dataclass(frozen=True)
class _EditResult:
    """The outcome of one Piece's edit — its artifact and any bar failure.

    Attributes:
        artifact: The best-effort artifact (the agent's output / cut result),
            persisted as ``piece.md`` whether or not it passed.
        failure_code: The failure code when a bar was not met, else None.
        detail: The failure detail (the violations / drift summary).
    """

    artifact: PieceArtifact
    failure_code: str | None
    detail: str


def _qa_loop(
    ctx: RunContext,
    artifact: PieceArtifact,
    banned: tuple[str, ...],
    voice: str,
    piece_spec: str,
) -> _EditResult:
    """Revise the draft via a bounded agent over ``check_guardrails``.

    The Editor agent loops draft → check → revise within one ``run_agent``
    call (bounded by ``agent_step_limit``), carrying the authored
    ``piece_spec + voice`` as its system prompt. The deterministic
    ``evaluate_piece`` — not the model's self-assessment — is the arbiter
    *after* the agent finishes; a Piece that still fails is reported as a
    ``QABudgetExceededError`` bar failure (collected, not raised) so the
    stage can route it to the human queue.

    Args:
        ctx: The run context.
        artifact: The draft artifact.
        banned: The banned-filler list.
        voice: The active Voice Profile text.
        piece_spec: The piece guardrail text.

    Returns:
        The edit result — the revised artifact and any bar failure.
    """
    topic_ids = tuple(artifact.topic_ids)
    tool = _check_guardrails_tool(ctx, artifact.id, topic_ids, banned, voice, piece_spec)
    revised = decode_piece_payload(
        ctx.llm.run_agent(
            LLMRequest(
                purpose="editor.qa",
                instructions=f"{piece_spec}\n\n---\n\n{voice}",
                payload={
                    "piece_id": artifact.id,
                    "title": artifact.title,
                    "teaser": artifact.teaser,
                    "read_time_min": artifact.read_time_min,
                    "blocks": _blocks_payload(artifact),
                },
            ),
            [tool],
            step_limit=ctx.config.agent_step_limit,
        ),
        piece_id=artifact.id,
        topic_ids=topic_ids,
        purpose="editor.qa",
    )
    residual = evaluate_piece(revised, banned)
    if residual:
        summary = "; ".join(f"{v.code}: {v.message}" for v in residual[:5])
        return _EditResult(
            revised,
            QABudgetExceededError.__name__,
            f"Piece {artifact.id!r} still fails after the agentic QA loop "
            f"(step_limit={ctx.config.agent_step_limit}): {summary}",
        )
    return _EditResult(revised, None, "")


def _blocks_payload(artifact: PieceArtifact) -> list[dict[str, object]]:
    """Represent an artifact's blocks as JSON-ready dicts.

    Args:
        artifact: The Piece.

    Returns:
        One dict per block, carrying kind + payload fields.
    """
    return [{"kind": str(block.kind), **dict(block.payload)} for block in artifact.blocks]


def _grounding_check(
    ctx: RunContext,
    concept: PieceConcept,
    artifact: PieceArtifact,
    banned: tuple[str, ...],
) -> _EditResult:
    """Stage 4.5 — map every assertion back to a verified claim; cut drift.

    Args:
        ctx: The run context.
        concept: The planned Piece.
        artifact: The edited artifact.
        banned: The banned-filler list (final re-check after a cut).

    Returns:
        The edit result — the grounded artifact and any bar failure
        (``GroundingDriftError`` if drift survives, ``QABudgetExceededError``
        if the cut re-broke the guardrails).
    """
    ledger = ledger_from_json(ctx.workspace.read(grounding_path(concept.id)))
    claims = [{"id": claim.id, "text": claim.text} for claim in ledger.verified_claims()]
    for attempt in range(2):
        unsupported = decode_object_list(
            ctx.llm.complete(
                LLMRequest(
                    purpose="editor.ground",
                    instructions=ctx.specs.guardrail_text("sourcing"),
                    payload={
                        "piece_id": artifact.id,
                        "text": artifact.all_text(),
                        "claims": claims,
                    },
                )
            ),
            key="unsupported",
            purpose="editor.ground",
        )
        if not unsupported:
            return _EditResult(artifact, None, "")
        if attempt == 1:
            drifted = "; ".join(str(item.get("text", "")) for item in unsupported[:3])
            return _EditResult(
                artifact,
                GroundingDriftError.__name__,
                f"Piece {artifact.id!r} still carries unsupported assertions "
                f"after the cut pass: {drifted}",
            )
        artifact = decode_piece_payload(
            ctx.llm.complete(
                LLMRequest(
                    purpose="editor.cut",
                    instructions=ctx.specs.guardrail_text("sourcing"),
                    payload={
                        "piece_id": artifact.id,
                        "title": artifact.title,
                        "teaser": artifact.teaser,
                        "read_time_min": artifact.read_time_min,
                        "blocks": _blocks_payload(artifact),
                        "unsupported": list(unsupported),
                        "claims": claims,
                    },
                )
            ),
            piece_id=artifact.id,
            topic_ids=tuple(artifact.topic_ids),
            purpose="editor.cut",
        )
        residual = evaluate_piece(artifact, banned)
        if residual:
            summary = "; ".join(f"{v.code}: {v.message}" for v in residual[:3])
            return _EditResult(
                artifact,
                QABudgetExceededError.__name__,
                f"Piece {artifact.id!r} re-broke the guardrails while cutting drift: {summary}",
            )
    return _EditResult(artifact, None, "")


def run_stage_wire(
    ctx: RunContext, output_path: str = CONNECTIONS, survivors: frozenset[str] | None = None
) -> None:
    """Stage 5 — the Weaver realizes every planned Connection with a passing hook.

    Also serves as the post-approval re-wire mode (ADR 0012) when
    ``survivors`` restricts the Piece set.

    Args:
        ctx: The run context.
        output_path: Where to write the wired Connections.
        survivors: When re-wiring, the approved Piece ids; None wires the
            full plan.

    Raises:
        QABudgetExceededError: If a hook cannot pass within the hook budget.
    """
    stage = ctx.manifest.stage("wire" if survivors is None else "rewire")
    plan = load_plan(ctx)
    concept_ids = [
        concept.id for concept in plan.concepts if survivors is None or concept.id in survivors
    ]
    ctx.workspace.require(stage.name, *expanded_prerequisites(stage, concept_ids))
    if ctx.workspace.exists(output_path):
        return
    brief = load_brief(ctx)
    voice = ctx.specs.voice_text(voice_name(ctx, brief))
    connection_spec = ctx.specs.guardrail_text("connection")
    banned = ctx.specs.banned_phrases()
    concepts = {concept.id: concept for concept in plan.concepts}
    keep = frozenset(concept_ids)
    edges: list[WiredConnection] = []
    for planned in plan.connections:
        if planned.from_piece_id not in keep or planned.to_piece_id not in keep:
            continue
        edges.append(_realize_hook(ctx, planned, concepts, edges, voice, connection_spec, banned))
    ctx.workspace.write(output_path, render_connections(tuple(edges)))


def _realize_hook(
    ctx: RunContext,
    planned: PlannedConnection,
    concepts: dict[str, PieceConcept],
    existing: list[WiredConnection],
    voice: str,
    connection_spec: str,
    banned: tuple[str, ...],
) -> WiredConnection:
    """Write one Connection's per-origin hook, retrying failed hooks.

    Args:
        ctx: The run context.
        planned: The planned edge (from plan.md).
        concepts: Concept lookup by id.
        existing: Edges already realized (for the set-level B3 check).
        voice: The active Voice Profile text.
        connection_spec: The connection guardrail text.
        banned: The banned-filler list.

    Returns:
        A wired Connection that passes the connection guardrails.

    Raises:
        QABudgetExceededError: If the hook budget is spent without a pass.
    """
    feedback: list[dict[str, object]] = []
    for _ in range(ctx.config.hook_budget + 1):
        response = decode_object(
            ctx.llm.complete(
                LLMRequest(
                    purpose="weaver.hook",
                    instructions=f"{connection_spec}\n\n---\n\n{voice}",
                    payload={
                        "from": {
                            "id": planned.from_piece_id,
                            "title": concepts[planned.from_piece_id].title,
                            "premise": concepts[planned.from_piece_id].premise,
                        },
                        "to": {
                            "id": planned.to_piece_id,
                            "title": concepts[planned.to_piece_id].title,
                            "premise": concepts[planned.to_piece_id].premise,
                        },
                        "hook_angle": planned.hook_angle,
                        "rationale": planned.rationale,
                        "violations": feedback,
                    },
                )
            ),
            purpose="weaver.hook",
        )
        candidate = WiredConnection(
            from_piece_id=planned.from_piece_id,
            to_piece_id=planned.to_piece_id,
            hook=str(response.get("hook", "")),
            rationale=str(response.get("rationale", planned.rationale)),
        )
        violations = [
            violation
            for violation in evaluate_connections((*existing, candidate), banned)
            if violation.subject in (candidate.subject(), f"->{candidate.to_piece_id}")
        ]
        if not violations:
            return candidate
        feedback = [{"code": v.code, "message": v.message} for v in violations]
    raise QABudgetExceededError(
        f"hook for {planned.from_piece_id}->{planned.to_piece_id} failed the connection "
        f"guardrails {ctx.config.hook_budget + 1} time(s): "
        + "; ".join(str(item["message"]) for item in feedback)
    )


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


def run_stage_qa(ctx: RunContext) -> tuple[str, ...]:
    """Stage 6 — the Reviewer asserts I1–I8 binary and judges J1–J5.

    Args:
        ctx: The run context.

    Returns:
        The escalated Tier-2 codes (flags for the human queue).

    Raises:
        ContractViolationError: If any Tier-1 invariant fails — a run
            either satisfies the outcome contract or fails, no soft
            warnings on the hard invariants.
    """
    stage = ctx.manifest.stage("qa")
    plan = load_plan(ctx)
    ctx.workspace.require(stage.name, *expanded_prerequisites(stage, plan.concept_ids()))
    if ctx.workspace.exists(QA):
        _, escalations = parse_qa_outcome(ctx.workspace.read(QA))
        return escalations
    constellation = assemble_constellation(ctx)
    banned = ctx.specs.banned_phrases()
    tier1 = evaluate_constellation(constellation, banned)
    judged = decode_object_list(
        ctx.llm.complete(
            LLMRequest(
                purpose="reviewer.tier2",
                instructions=ctx.specs.guardrail_text("constellation"),
                payload={
                    "concepts": [
                        {
                            "id": concept.id,
                            "title": concept.title,
                            "premise": concept.premise,
                            "topics": list(concept.topic_ids),
                            "entry_worthy": concept.entry_worthy,
                        }
                        for concept in plan.concepts
                    ],
                    "connections": [
                        {"from": edge.from_piece_id, "to": edge.to_piece_id, "hook": edge.hook}
                        for edge in constellation.connections
                    ],
                },
            )
        ),
        key="judgements",
        purpose="reviewer.tier2",
    )
    tier2 = tuple(
        Tier2Judgement(
            code=str(item.get("code", "")),
            passed=bool(item.get("passed", False)),
            note=str(item.get("note", "")),
        )
        for item in judged
    )
    escalations = tuple(judgement.code for judgement in tier2 if not judgement.passed)
    ctx.workspace.write(
        QA, render_qa_report(QAReport(tier1=tier1, tier2=tier2, escalations=escalations))
    )
    if not tier1.passed:
        raise ContractViolationError(
            f"Tier-1 outcome contract failed: {', '.join(tier1.failed_codes())} — see qa.md"
        )
    return escalations

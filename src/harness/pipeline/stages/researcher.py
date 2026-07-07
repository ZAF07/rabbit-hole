"""The Researcher — Stage 2, closed-book sourcing, per planned Piece.

Harvest (recall proposes claims + candidate URLs) → agentic navigation of
cited outlinks → Vet each page → Corroborate against the bar → Refute
survivors. The corroboration bar lives here because it is sourcing-local; the
deterministic checks stay the arbiter of admission (ADR 0005, ADR 0011).
"""

import json
from collections.abc import Mapping, Sequence
from threading import Lock as _Lock

from harness.domain.grounding import (
    ClaimRecord,
    ClaimStatus,
    GroundingLedger,
    RefutationVerdict,
    SourceRecord,
    SourceTier,
)
from harness.domain.grounding_io import ledger_to_json
from harness.domain.plan import PieceConcept
from harness.errors import LLMResponseError, ThinSourcePackError
from harness.pipeline.context import RunContext
from harness.pipeline.decode import decode_object, decode_object_list
from harness.pipeline.stages._kernel import _fan_out, grounding_path, load_plan, sources_path
from harness.ports.llm import LLMRequest, ToolSpec
from harness.ports.web_source import FetchedPage


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

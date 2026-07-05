"""The deterministic LangGraph ``StateGraph`` — hand-built control flow.

Fixed stage order (0 Gate → 1 Plan → 2 Source → 3 Draft → 4 Edit → 5 Wire →
6 Constellation QA → re-wire → re-QA → write), the Stage-0 short-circuit,
and the three human gates as pause points — not a free-roaming supervisor
(ADR 0010). This runtime is authoritative for the outcome-contract
guarantee; every node delegates its decision to the shared transitions in
:mod:`harness.pipeline.steps`, so the Claude Code wiring behaves
identically over the same specs + manifest.
"""

from typing import Any, TypedDict, cast

from langgraph.graph import END, START, StateGraph

from harness.pipeline import stages, steps
from harness.pipeline.context import RunContext


class RunState(TypedDict, total=False):
    """The thin progress state the graph carries between nodes.

    Everything substantive lives on disk in the run workspace — the
    deliverable-on-disk is the gate; this state only tracks control flow.
    """

    status: str
    detail: str
    rejected_pieces: list[str]
    flagged_pieces: list[str]
    escalations: list[str]
    published: list[str]
    survivors: list[str]


def _running(state: RunState) -> bool:
    """Whether the run is still proceeding (not failed/paused/rejected).

    Args:
        state: The current state.

    Returns:
        True while the run should continue.
    """
    return state.get("status", "running") == "running"


def build_pipeline(ctx: RunContext) -> Any:
    """Assemble and compile the staged graph for one run.

    Args:
        ctx: The run's wiring.

    Returns:
        The compiled LangGraph graph.
    """
    graph: StateGraph[RunState, None, RunState, RunState] = StateGraph(RunState)

    def gate0(state: RunState) -> RunState:
        """Stage 0 — refuse the run on missing DNA/Brief or placeholders."""
        return cast(RunState, steps.gate0_update(ctx))

    def plan(state: RunState) -> RunState:
        """Stage 1 — the Architect."""
        stages.run_stage_plan(ctx)
        return {}

    def gate_plan(state: RunState) -> RunState:
        """Human gate 1 — the plan (ADR 0013)."""
        return cast(RunState, steps.human_gate_update(ctx, ctx.manifest.human_gate("plan")))

    def source(state: RunState) -> RunState:
        """Stage 2 — the Researcher, per Piece."""
        stages.run_stage_source(ctx)
        return {}

    def draft(state: RunState) -> RunState:
        """Stage 3 — the Writer, per Piece."""
        stages.run_stage_draft(ctx)
        return {}

    def edit(state: RunState) -> RunState:
        """Stage 4 — the Editor, per Piece."""
        stages.run_stage_edit(ctx)
        return {}

    def wire(state: RunState) -> RunState:
        """Stage 5 — the Weaver."""
        stages.run_stage_wire(ctx)
        return {}

    def qa(state: RunState) -> RunState:
        """Stage 6 — Constellation QA."""
        return cast(RunState, steps.qa_update(ctx))

    def gate_pieces(state: RunState) -> RunState:
        """Human gate 2 — every Piece, approve / edit-approve / reject."""
        return cast(RunState, steps.human_gate_update(ctx, ctx.manifest.human_gate("piece")))

    def rewire(state: RunState) -> RunState:
        """Publish step — the Weaver's second mode over the approved subset."""
        return cast(RunState, steps.rewire_update(ctx, state))

    def reqa(state: RunState) -> RunState:
        """Publish step — the Reviewer's second mode; flags the unfixable."""
        return cast(RunState, steps.reqa_update(ctx, state))

    def gate_constellation(state: RunState) -> RunState:
        """Human gate 3 — the wired constellation, before the write."""
        return cast(
            RunState, steps.human_gate_update(ctx, ctx.manifest.human_gate("constellation"))
        )

    def write(state: RunState) -> RunState:
        """Publish step — atomic write of the re-validated survivor set."""
        return cast(RunState, steps.write_update(ctx, state))

    ordered = (
        ("gate0", gate0),
        ("plan", plan),
        ("gate_plan", gate_plan),
        ("source", source),
        ("draft", draft),
        ("edit", edit),
        ("wire", wire),
        ("qa", qa),
        ("gate_pieces", gate_pieces),
        ("rewire", rewire),
        ("reqa", reqa),
        ("gate_constellation", gate_constellation),
        ("write", write),
    )
    for name, node in ordered:
        graph.add_node(name, node)
    graph.add_edge(START, "gate0")
    for (name, _), (successor, _) in zip(ordered, ordered[1:], strict=False):
        graph.add_conditional_edges(
            name,
            lambda state, nxt=successor: nxt if _running(state) else END,
        )
    graph.add_edge("write", END)
    return graph.compile()


def run_pipeline(ctx: RunContext) -> RunState:
    """Run (or resume) the pipeline for one run workspace.

    Completed stages skip on their existing deliverables, so re-invoking
    after a pause continues from the first missing artifact.

    Args:
        ctx: The run's wiring.

    Returns:
        The final run state.
    """
    compiled = build_pipeline(ctx)
    initial: RunState = {"status": "running"}
    return cast(RunState, compiled.invoke(initial))

"""The manifest-driven orchestrator — the Claude Code runtime's structural twin.

Where the LangGraph runtime hand-builds its ``StateGraph``, this runner walks
``harness/manifest.toml`` generically: stages in manifest order, each human
gate fired after the stage the manifest declares. Every decision is made by
the shared transitions in :mod:`harness.pipeline.steps`, so only the wiring
differs between runtimes and the parity test holds them to identical
behavior (ADR 0010, ADR 0013).
"""

from collections.abc import Callable

from harness.pipeline import stages, steps
from harness.pipeline.context import RunContext


def _simple(
    run: Callable[[RunContext], None],
) -> Callable[[RunContext, steps.RunStateView], dict[str, object]]:
    """Wrap a stage function that carries no state update as a handler.

    Args:
        run: The stage function.

    Returns:
        A dispatch handler returning an empty update.
    """

    def handler(ctx: RunContext, state: steps.RunStateView) -> dict[str, object]:
        """Run the stage and report no state change.

        Args:
            ctx: The run's wiring.
            state: The accumulated run state (unused).

        Returns:
            An empty update.
        """
        run(ctx)
        return {}

    return handler


_DISPATCH: dict[str, Callable[[RunContext, steps.RunStateView], dict[str, object]]] = {
    "gate": lambda ctx, state: steps.gate0_update(ctx),
    "plan": _simple(stages.run_stage_plan),
    "source": _simple(stages.run_stage_source),
    "draft": _simple(stages.run_stage_draft),
    "edit": _simple(stages.run_stage_edit),
    "wire": _simple(stages.run_stage_wire),
    "qa": lambda ctx, state: steps.qa_update(ctx),
    "rewire": steps.rewire_update,
    "reqa": steps.reqa_update,
    "write": steps.write_update,
}


def run_manifest_pipeline(ctx: RunContext) -> dict[str, object]:
    """Run (or resume) the pipeline by walking the stage manifest.

    Same resume semantics as the LangGraph runtime: completed stages skip
    on their existing deliverables, so re-invoking after a pause continues
    from the first missing artifact.

    Args:
        ctx: The run's wiring.

    Returns:
        The final run state.
    """
    state: dict[str, object] = {"status": "running"}
    for stage in ctx.manifest.stages:
        state.update(_DISPATCH[stage.name](ctx, state))
        if state["status"] != "running":
            return state
        for gate in ctx.manifest.human_gates:
            if gate.after_stage == stage.name:
                state.update(steps.human_gate_update(ctx, gate))
                if state["status"] != "running":
                    return state
    return state

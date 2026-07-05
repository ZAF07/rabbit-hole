"""Wires the generation pipeline behind the admin trigger's runner seam.

This is the **one** api module that imports the harness — the composition point
where the admin trigger meets ``run_pipeline``. It builds a ``RunContext`` per
run from injected ports (Content Graph, LLM, web) and drives the existing
pipeline; nothing here leaks generation concepts back to the reader, and the
reader modules import none of this (ADR 0006, ADR 0015). The harness reaches
Postgres / LLM / web only through those ports.
"""

from collections.abc import Callable
from pathlib import Path

from api.generation import GenerationService, Spawn
from content_graph.ports.repository import ContentGraphRepository
from harness.pipeline.context import HarnessConfig, RunContext
from harness.pipeline.graph import run_pipeline
from harness.ports.llm import LLMPort
from harness.ports.web_source import WebSourcePort
from harness.review.gates import GatePolicy
from harness.specs import SpecLibrary
from harness.workspace import RunWorkspace


def build_generation_service(
    *,
    repo: ContentGraphRepository,
    llm: LLMPort,
    web: WebSourcePort,
    gates: GatePolicy,
    specs: SpecLibrary,
    runs_root: Path,
    config: HarnessConfig | None = None,
    spawn: Spawn | None = None,
    id_factory: Callable[[], str] | None = None,
) -> GenerationService:
    """Build a generation service whose runner drives the harness pipeline.

    Args:
        repo: The Content Graph the pipeline reads for dedup and writes at
            publish — the only coupling to consumption's store.
        llm: The model port (a scripted adapter until a production one lands).
        web: The web-sourcing port.
        gates: The human-gate policy; an unattended trigger proceeds to the
            first gate under it.
        specs: The markdown source of truth (Editorial DNA, voices, manifest).
        runs_root: The directory each run's workspace is created beneath.
        config: The run's knobs; a default is used when omitted.
        spawn: How the run is dispatched off the request path; a background
            thread by default.
        id_factory: Mints run ids; random UUIDs by default.

    Returns:
        A generation service ready to mount behind the admin router.
    """
    resolved_config = config or HarnessConfig()

    def runner(run_id: str, brief: str) -> object:
        workspace = RunWorkspace(runs_root / run_id)
        workspace.write("goal.md", brief)
        context = RunContext(
            run_id=run_id,
            workspace=workspace,
            specs=specs,
            manifest=specs.manifest(),
            llm=llm,
            web=web,
            repo=repo,
            gates=gates,
            config=resolved_config,
        )
        return run_pipeline(context)

    return GenerationService(runner, spawn=spawn, id_factory=id_factory)

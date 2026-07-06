"""Wires the generation pipeline behind the admin trigger's runner seam.

This is the **one** api module that imports the harness — the composition point
where the admin trigger meets ``run_pipeline``. It builds a ``RunContext`` per
run from injected ports (Content Graph, LLM, web) and drives the existing
pipeline; nothing here leaks generation concepts back to the reader, and the
reader modules import none of this (ADR 0006, ADR 0015). The harness reaches
Postgres / LLM / web only through those ports.
"""

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from api.generation import GenerationService, Spawn
from content_graph.ports.repository import ContentGraphRepository
from harness.pipeline.context import HarnessConfig, RunContext
from harness.pipeline.graph import run_pipeline
from harness.ports.llm import LLMPort
from harness.ports.web_source import WebSourcePort
from harness.review.gates import GatePolicy
from harness.specs import SpecLibrary
from harness.workspace import RunWorkspace

USAGE = "usage.json"


class UsageRecord(Protocol):
    """The per-call usage shape an adapter accumulates (structural, provider-agnostic).

    A scripted LLM exposes no ``usage`` at all (its runs write an empty
    report); a production adapter exposes a list of records matching this
    shape. Kept structural so ``harness_runner`` never imports a provider type.

    Attributes:
        tier: The tier the call went out on (``precise``/``creative``).
        model: The model-id the call used.
        input_tokens: Prompt tokens reported.
        output_tokens: Completion tokens reported.
    """

    tier: str
    model: str
    input_tokens: int
    output_tokens: int


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
        before = len(_usage_of(llm))
        try:
            return run_pipeline(context)
        finally:
            _write_usage(workspace, run_id, _usage_of(llm)[before:])

    return GenerationService(runner, spawn=spawn, id_factory=id_factory)


def _usage_of(llm: LLMPort) -> Sequence[UsageRecord]:
    """The usage records an adapter has accumulated, or empty for one with none.

    Args:
        llm: The model port; only a production adapter exposes ``usage``.

    Returns:
        The accumulated records (empty when the adapter tracks no usage).
    """
    records: Sequence[UsageRecord] = getattr(llm, "usage", ())
    return records


def _write_usage(workspace: RunWorkspace, run_id: str, records: Sequence[UsageRecord]) -> None:
    """Write a run's ``usage.json`` — model calls and tokens, aggregated per tier.

    Provider-agnostic via the structural :class:`UsageRecord`: a scripted LLM
    with no usage yields an empty report, a production adapter yields real
    DeepSeek spend, and neither is imported here by type.

    Args:
        workspace: The run's file workspace.
        run_id: The run identity.
        records: The per-call usage records the adapter accumulated this run.
    """
    models: dict[str, str] = {}
    calls: dict[str, int] = {}
    input_tokens: dict[str, int] = {}
    output_tokens: dict[str, int] = {}
    for record in records:
        tier = record.tier
        models.setdefault(tier, record.model)
        calls[tier] = calls.get(tier, 0) + 1
        input_tokens[tier] = input_tokens.get(tier, 0) + record.input_tokens
        output_tokens[tier] = output_tokens.get(tier, 0) + record.output_tokens
    by_tier = {
        tier: {
            "model": models[tier],
            "calls": calls[tier],
            "input_tokens": input_tokens[tier],
            "output_tokens": output_tokens[tier],
        }
        for tier in sorted(calls)
    }
    report = {"run_id": run_id, "calls": len(records), "by_tier": by_tier}
    workspace.write(USAGE, json.dumps(report, indent=2) + "\n")

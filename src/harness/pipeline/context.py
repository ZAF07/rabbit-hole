"""The wiring one run carries — ports, specs, workspace, and knobs."""

from dataclasses import dataclass, field

from content_graph.ports.repository import ContentGraphRepository
from harness.manifest import StageManifest
from harness.ports.llm import LLMPort
from harness.ports.web_source import WebSourcePort
from harness.review.gates import GatePolicy
from harness.specs import SpecLibrary
from harness.workspace import RunWorkspace


@dataclass(frozen=True)
class HarnessConfig:
    """The run's tunable knobs.

    Attributes:
        default_voice: Voice Profile used when the Brief names none.
        min_verified_claims: The thin-pack bar — fewer verified claims than
            this fails the Piece before the Writer runs.
        hook_budget: Maximum Weaver retries for one failing hook.
        agent_step_limit: The step budget for a bounded-worker agent
            (the Researcher's navigation and the Editor's revision loops),
            passed to ``run_agent`` as its ``recursion_limit`` — it also
            bounds how far the Researcher's citation-chase may walk.
        fan_out: The per-Piece concurrency bound for Source, Draft, and Edit
            (a within-stage barrier). ``1`` runs serially; raise it to
            parallelize a real run against provider rate limits. Concurrency
            is an efficiency change only — deliverables are byte-identical to
            a serial run.
        runtime: The orchestrator's name, recorded in every verdict line.
        model: The model identity, recorded in every verdict line.
    """

    default_voice: str = "narrative-nonfiction"
    min_verified_claims: int = 2
    hook_budget: int = 2
    agent_step_limit: int = 6
    fan_out: int = 1
    runtime: str = "langgraph"
    model: str = "unspecified"


@dataclass(frozen=True)
class RunContext:
    """Everything a stage needs, injected once per run.

    Attributes:
        run_id: The run's identity (also its workspace directory name).
        workspace: The run's file workspace.
        specs: The markdown source of truth.
        manifest: The shared stage manifest.
        llm: The model port.
        web: The web-sourcing port.
        repo: The Content Graph port (read for dedup, write at publish).
        gates: The human-gate policy.
        config: The run's knobs.
    """

    run_id: str
    workspace: RunWorkspace
    specs: SpecLibrary
    manifest: StageManifest
    llm: LLMPort
    web: WebSourcePort
    repo: ContentGraphRepository
    gates: GatePolicy
    config: HarnessConfig = field(default_factory=HarnessConfig)

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
        qa_budget: Maximum Editor re-edit rounds before escalation.
        min_verified_claims: The thin-pack bar — fewer verified claims than
            this fails the Piece before the Writer runs.
        citation_depth: How many link hops the Researcher may chase from a
            recalled hub page.
        citation_limit: Maximum chased links per fetched page.
        hook_budget: Maximum Weaver retries for one failing hook.
        runtime: The orchestrator's name, recorded in every verdict line.
        model: The model identity, recorded in every verdict line.
    """

    default_voice: str = "narrative-nonfiction"
    qa_budget: int = 3
    min_verified_claims: int = 2
    citation_depth: int = 1
    citation_limit: int = 4
    hook_budget: int = 2
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

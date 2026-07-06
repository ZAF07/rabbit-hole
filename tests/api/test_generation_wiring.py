"""Issue 06 — the admin trigger goes live by config; each run writes usage.json."""

import json
from collections.abc import Callable, Sequence
from pathlib import Path

from tests.harness.fixture_run import (
    FIXTURE_GOAL,
    REPO_ROOT,
    fixture_web_source,
    well_behaved_llm,
)

from api.harness_runner import build_generation_service
from api.main import generation_configured
from content_graph.adapters.memory import InMemoryContentGraphRepository
from harness.adapters.deepseek import CallUsage, tier_for
from harness.adapters.fakes import ScriptedLLM
from harness.ports.llm import LLMRequest, ToolSpec
from harness.review.gates import AutoApproveGates
from harness.specs import SpecLibrary


class UsageLLM(ScriptedLLM):
    """A scripted LLM that records per-call usage, like the real adapter does."""

    def __init__(self, handlers: dict, agent_handlers: dict) -> None:
        super().__init__(handlers, agent_handlers)
        self.usage: list[CallUsage] = []

    def complete(self, request: LLMRequest) -> str:
        out = super().complete(request)
        tier = tier_for(request.purpose)
        self.usage.append(CallUsage(request.purpose, tier, f"deepseek-{tier}", 11, 22))
        return out

    def run_agent(self, request: LLMRequest, tools: Sequence[ToolSpec], *, step_limit: int) -> str:
        out = super().run_agent(request, tools, step_limit=step_limit)
        tier = tier_for(request.purpose)
        self.usage.append(CallUsage(request.purpose, tier, f"deepseek-{tier}", 3, 7))
        return out


def _synchronous_spawn(thunk: Callable[[], None]) -> None:
    thunk()


def test_generation_is_live_only_when_provider_and_admin_token_are_both_set():
    assert generation_configured({"LLM_PROVIDER": "deepseek", "API_ADMIN_TOKEN": "s"}) is True
    assert generation_configured({"LLM_PROVIDER": "deepseek"}) is False
    assert generation_configured({"API_ADMIN_TOKEN": "s"}) is False
    assert generation_configured({}) is False
    assert generation_configured({"LLM_PROVIDER": "  ", "API_ADMIN_TOKEN": "s"}) is False


def test_each_run_writes_a_usage_json_aggregated_per_tier(tmp_path: Path):
    base = well_behaved_llm()
    llm = UsageLLM(base._handlers, base._agent_handlers)
    service = build_generation_service(
        repo=InMemoryContentGraphRepository(),
        llm=llm,
        web=fixture_web_source(),
        gates=AutoApproveGates(),
        specs=SpecLibrary(repo_root=REPO_ROOT),
        runs_root=tmp_path,
        spawn=_synchronous_spawn,
        id_factory=lambda: "run-1",
    )
    record = service.launch(FIXTURE_GOAL)
    assert record.run_id == "run-1"

    usage = json.loads((tmp_path / "run-1" / "usage.json").read_text())
    assert usage["run_id"] == "run-1"
    assert usage["calls"] > 0
    assert set(usage["by_tier"]) == {"precise", "creative"}
    for tier, bucket in usage["by_tier"].items():
        assert bucket["model"] == f"deepseek-{tier}"
        assert bucket["calls"] > 0
        assert bucket["input_tokens"] > 0
        assert bucket["output_tokens"] > 0
    assert usage["calls"] == sum(b["calls"] for b in usage["by_tier"].values())

"""Issue 01 — the run_agent seam: ToolSpec, the port method, and the fake driving tools."""

import json

import pytest

from harness.adapters.fakes import FakeWebSource, ScriptedLLM
from harness.ports.llm import LLMPort, LLMRequest, ToolSpec
from harness.ports.web_source import FetchedPage


def test_llmport_declares_run_agent_alongside_complete():
    abstract = LLMPort.__abstractmethods__
    assert "complete" in abstract
    assert "run_agent" in abstract


def test_toolspec_is_a_frozen_framework_neutral_dataclass():
    spec = ToolSpec(
        name="echo",
        description="echoes its args",
        parameters={"type": "object", "properties": {}},
        run=lambda args: json.dumps(args),
    )
    assert spec.run({"x": 1}) == '{"x": 1}'
    with pytest.raises(AttributeError):
        spec.name = "other"  # type: ignore[misc]


def test_scripted_run_agent_invokes_tool_callables_and_records_request():
    web = FakeWebSource({"u": FetchedPage(url="u", content="body", outlinks=())})
    fetch_tool = ToolSpec(
        name="fetch",
        description="fetch a url",
        parameters={"type": "object", "properties": {"url": {"type": "string"}}},
        run=lambda args: page.content if (page := web.fetch(str(args["url"]))) else "none",
    )

    def nav(request, tools, step_limit):
        tool = next(t for t in tools if t.name == "fetch")
        seen = tool.run({"url": "u"})
        return json.dumps({"reached": seen, "budget": step_limit})

    llm = ScriptedLLM()
    llm.on_agent("researcher.navigate", nav)
    request = LLMRequest(purpose="researcher.navigate", instructions="spec", payload={})

    result = json.loads(llm.run_agent(request, [fetch_tool], step_limit=7))

    assert result == {"reached": "body", "budget": 7}
    assert web.fetched == ["u"]
    assert llm.requests == [request]


def test_scripted_run_agent_without_handler_raises():
    llm = ScriptedLLM()
    with pytest.raises(KeyError):
        llm.run_agent(LLMRequest(purpose="unknown"), [], step_limit=3)

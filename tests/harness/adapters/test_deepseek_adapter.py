"""Issue 02 — the DeepSeek adapter's ``complete`` over a recorded HTTP transport.

No real DeepSeek is ever hit: an ``httpx.MockTransport`` is injected into the
``ChatDeepSeek`` client, so the tests assert exactly what goes out on the wire
(JSON mode, the per-purpose tier) and what the adapter does with what comes
back (repair/transport retry, loud failure on a persistent malformation).
"""

import json
import os
import subprocess
import sys

import httpx
import pytest

pytest.importorskip("langchain_deepseek")

from harness.adapters.deepseek import (  # noqa: E402
    DeepSeekLLM,
    UnsupportedModelError,
    tier_for,
)
from harness.adapters.llm_factory import build_llm  # noqa: E402
from harness.config import LLMConfig, LLMTier  # noqa: E402
from harness.errors import LLMResponseError  # noqa: E402
from harness.ports.llm import LLMRequest, ToolSpec  # noqa: E402

FLASH = LLMTier(model="deepseek-v4-flash", temperature=0.0)
PRO = LLMTier(model="deepseek-v4-pro", temperature=1.3)


def config() -> LLMConfig:
    return LLMConfig(provider="deepseek", api_key="sk-test", precise=FLASH, creative=PRO)


def completion(content: str, model: str = "m") -> dict:
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
    }


class ScriptedTransport:
    """A MockTransport handler replaying a queue of contents/exceptions, recording bodies."""

    def __init__(self, behaviors: list) -> None:
        self.behaviors = list(behaviors)
        self.requests: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        behavior = self.behaviors.pop(0)
        if isinstance(behavior, Exception):
            raise behavior
        return httpx.Response(200, json=completion(behavior))


def adapter(behaviors: list, *, repair_retries: int = 2) -> tuple[DeepSeekLLM, ScriptedTransport]:
    handler = ScriptedTransport(behaviors)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return (
        DeepSeekLLM(config(), http_client=client, repair_retries=repair_retries),
        handler,
    )


def test_tier_classification_splits_prose_from_structural():
    assert tier_for("architect.plan") == "precise"
    assert tier_for("editor.judge") == "precise"
    assert tier_for("researcher.navigate") == "precise"
    assert tier_for("writer.draft") == "creative"
    assert tier_for("editor.qa") == "creative"
    assert tier_for("weaver.hook") == "creative"


def test_complete_sends_json_mode_and_precise_tier_for_structural_purpose():
    llm, handler = adapter(['{"ok": true}'])
    out = llm.complete(LLMRequest(purpose="architect.plan", instructions="spec"))
    assert json.loads(out) == {"ok": True}
    body = handler.requests[0]
    assert body["model"] == "deepseek-v4-flash"
    assert body["temperature"] == 0.0
    assert body["response_format"] == {"type": "json_object"}


def test_complete_selects_creative_tier_for_prose_purpose():
    llm, handler = adapter(['{"title": "x"}'])
    llm.complete(LLMRequest(purpose="writer.draft", instructions="spec"))
    body = handler.requests[0]
    assert body["model"] == "deepseek-v4-pro"
    assert body["temperature"] == 1.3


def test_repair_retry_recovers_from_malformed_then_valid():
    llm, handler = adapter(["not json at all", '{"ok": true}'])
    out = llm.complete(LLMRequest(purpose="architect.plan"))
    assert json.loads(out) == {"ok": True}
    assert len(handler.requests) == 2


def test_transport_retry_recovers_from_connection_error_then_success():
    llm, handler = adapter([httpx.ConnectError("boom"), '{"ok": true}'])
    out = llm.complete(LLMRequest(purpose="architect.plan"))
    assert json.loads(out) == {"ok": True}
    assert len(handler.requests) == 2


def test_persistently_malformed_raises_llm_response_error():
    llm, handler = adapter(["nope", "still nope", "nope again"], repair_retries=2)
    with pytest.raises(LLMResponseError):
        llm.complete(LLMRequest(purpose="architect.plan"))
    assert len(handler.requests) == 3


def test_persistent_transport_failure_is_not_an_llm_response_error():
    errors = [httpx.ConnectError("boom")] * 3
    llm, _ = adapter(errors, repair_retries=2)
    with pytest.raises(Exception) as excinfo:
        llm.complete(LLMRequest(purpose="architect.plan"))
    assert not isinstance(excinfo.value, LLMResponseError)


def test_usage_is_recorded_per_call_with_tier_and_model():
    llm, _ = adapter(['{"ok": true}'])
    llm.complete(LLMRequest(purpose="writer.draft"))
    assert len(llm.usage) == 1
    record = llm.usage[0]
    assert record.tier == "creative"
    assert record.model == "deepseek-v4-pro"
    assert record.input_tokens == 3
    assert record.output_tokens == 5


def test_build_llm_returns_deepseek_adapter_for_deepseek_provider():
    llm = build_llm(config())
    assert isinstance(llm, DeepSeekLLM)


def test_build_time_capability_check_rejects_incapable_model():
    bad = LLMConfig(
        provider="deepseek",
        api_key="sk",
        precise=LLMTier(model="deepseek-reasoner", temperature=0.0),
        creative=PRO,
    )
    with pytest.raises(UnsupportedModelError) as excinfo:
        DeepSeekLLM(bad)
    assert "deepseek-reasoner" in str(excinfo.value)


def test_adapter_module_imports_offline_without_pulling_in_langchain():
    code = (
        "import sys\n"
        "import harness.adapters.deepseek\n"
        "import harness.adapters.llm_factory\n"
        "leaked = sorted(m for m in sys.modules if 'langchain' in m or m == 'openai')\n"
        "assert not leaked, leaked\n"
        "print('ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=os.getcwd(),
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def tool_call_completion(name: str, arguments: dict, model: str = "m") -> dict:
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(arguments)},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
    }


class AgentTransport:
    """Emits a tool call, then a final JSON answer; records tool invocations."""

    def __init__(self) -> None:
        self.step = 0
        self.tool_args_seen: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.step += 1
        if self.step == 1:
            return httpx.Response(200, json=tool_call_completion("fetch", {"url": "u"}))
        return httpx.Response(200, json=completion('{"reached": "primary"}'))


def test_run_agent_runs_the_tool_loop_and_returns_decodable_json():
    handler = AgentTransport()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = DeepSeekLLM(config(), http_client=client)

    invoked: list[dict] = []

    def run_fetch(args):
        invoked.append(dict(args))
        return "PRIMARY PAGE"

    fetch_tool = ToolSpec(
        name="fetch",
        description="fetch a url",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        run=run_fetch,
    )
    out = llm.run_agent(
        LLMRequest(purpose="editor.qa", instructions="revise"),
        [fetch_tool],
        step_limit=6,
    )
    assert json.loads(out) == {"reached": "primary"}
    assert invoked == [{"url": "u"}]
    assert handler.step == 2


def test_run_agent_uses_the_creative_tier_for_the_editor():
    seen_models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_models.append(json.loads(request.content)["model"])
        return httpx.Response(200, json=completion('{"done": true}'))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = DeepSeekLLM(config(), http_client=client)
    llm.run_agent(LLMRequest(purpose="editor.qa", instructions="revise"), [], step_limit=4)
    assert seen_models and all(model == "deepseek-v4-pro" for model in seen_models)


@pytest.mark.skipif(
    not os.environ.get("LLM_LIVE_TEST"),
    reason="live smoke test spends real DeepSeek budget; set LLM_LIVE_TEST + real key to run",
)
def test_live_smoke_completes_a_real_call():
    llm = build_llm(LLMConfig.from_env())
    out = llm.complete(
        LLMRequest(
            purpose="architect.plan",
            instructions="Reply with a JSON object containing a single key 'ok' set to true.",
        )
    )
    assert isinstance(json.loads(out), dict)

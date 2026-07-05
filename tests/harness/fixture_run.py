"""The shared fixture run: a 4-Piece Brief + well-behaved fakes for every port.

This is the offline substrate the end-to-end, parity, and review tests all
drive. The scripted handlers emit well-formed deliverable content for the
fixture Brief; individual tests override single purposes to inject failure
behavior.
"""

import json
from pathlib import Path

from content_graph.adapters.memory import InMemoryContentGraphRepository
from content_graph.ports.repository import ContentGraphRepository
from harness.adapters.fakes import FakeWebSource, ScriptedLLM
from harness.pipeline.context import HarnessConfig, RunContext
from harness.ports.llm import LLMRequest
from harness.ports.web_source import FetchedPage
from harness.review.gates import AutoApproveGates, GatePolicy
from harness.specs import SpecLibrary
from harness.workspace import RunWorkspace

REPO_ROOT = Path(__file__).resolve().parents[2]
FETCHED_AT = "2026-07-05T00:00:00Z"

FIXTURE_GOAL = """---
through_line: >
  The invisible systems that move the physical world, and how one failure
  in any of them cascades into all the others.
target_topics:
  - logistics
  - semiconductors
  - financial-systems
  - chokepoints
piece_count: 4
entry_hints:
  - The container piece should open cold as a Daily Feature.
---

## Notes to the Architect

Lead with a ship, a chip, a ledger, a strait. Keep it structural.
"""

PIECE_IDS = ("p-container", "p-chip", "p-money", "p-strait")

FIXTURE_PIECES: dict[str, dict] = {
    "p-container": {
        "title": "The Box That Ate the Waterfront",
        "teaser": "Fifty-eight aluminium boxes left Newark in 1956 and quietly rewired trade.",
        "premise": (
            "Malcom McLean's 1956 Ideal-X sailing collapsed the cost of moving goods "
            "and rebuilt every port on earth around a standard box."
        ),
        "claims": (
            {
                "id": "p-container-c1",
                "text": "The Ideal-X carried 58 containers from Newark to Houston "
                "on 26 April 1956.",
                "load_bearing": True,
            },
            {
                "id": "p-container-c2",
                "text": "Loading loose cargo cost $5.86 a ton in 1956; container "
                "loading cost 16 cents.",
                "load_bearing": False,
            },
        ),
        "paragraphs": (
            "On 26 April 1956, a converted tanker called the Ideal-X slipped out of Newark "
            "with 58 aluminium boxes bolted to its deck, and Malcom McLean stood on the pier "
            "watching his idea float.",
            "The arithmetic was brutal: loading loose cargo cost $5.86 a ton that year, while "
            "craning a sealed container aboard cost 16 cents, and the longshoremen who priced "
            "the difference knew exactly what it meant.",
            "So what happens when the box meets a chip fab that cannot wait?",
        ),
    },
    "p-chip": {
        "title": "Three Nanometres of Geography",
        "teaser": "The world's most advanced chips come from one company on one island.",
        "premise": (
            "TSMC's near-monopoly on advanced logic chips concentrates the digital world's "
            "supply into a handful of buildings reached by ship."
        ),
        "claims": (
            {
                "id": "p-chip-c1",
                "text": "TSMC produced roughly 90 percent of the world's most "
                "advanced logic chips in 2021.",
                "load_bearing": True,
            },
            {
                "id": "p-chip-c2",
                "text": "An ASML EUV machine cost about $150 million in 2021 and "
                "shipped in 40 freight containers.",
                "load_bearing": False,
            },
        ),
        "paragraphs": (
            "In a fab outside Hsinchu in 2021, machines the size of buses etched circuits three "
            "nanometres wide while the rest of the planet discovered it had outsourced its "
            "future to one company, TSMC.",
            "Each EUV machine that ASML shipped that year cost about $150 million and arrived, "
            "fittingly, in 40 freight containers — the box delivering the tool that makes the "
            "modern world.",
            "Who pays when a single building on one island sneezes?",
        ),
    },
    "p-money": {
        "title": "The Ledger Beneath the Cargo",
        "teaser": "Every box on every ship is also a line of credit moving at 17 knots.",
        "premise": (
            "Trade finance — letters of credit and open-account promises — is the invisible "
            "counterparty to every sailing, and it seizes when ships stop."
        ),
        "claims": (
            {
                "id": "p-money-c1",
                "text": "About 80 percent of world goods trade moved on "
                "trade-finance instruments in 2020.",
                "load_bearing": True,
            },
            {
                "id": "p-money-c2",
                "text": "The 2021 Ever Given grounding held up an estimated "
                "$9.6 billion of trade per day.",
                "load_bearing": False,
            },
        ),
        "paragraphs": (
            "When the Ever Given wedged into the sand in March 2021, bankers in London felt it "
            "before the tugboats did: an estimated $9.6 billion of trade sat pinned behind her "
            "stern every single day.",
            "Most of that cargo belonged to no one outright; it moved on letters of credit, and "
            "in 2020 about 80 percent of world goods trade still ran on such instruments.",
            "And what happens to a paper promise when the canal itself closes?",
        ),
    },
    "p-strait": {
        "title": "Six Miles Wide, a Fifth of the World's Oil",
        "teaser": "The Strait of Hormuz moves 21 million barrels a day through 21 miles.",
        "premise": (
            "A few narrow sea lanes concentrate the world's energy and cargo; Hormuz alone "
            "carries about a fifth of global oil consumption daily."
        ),
        "claims": (
            {
                "id": "p-strait-c1",
                "text": "About 21 million barrels of oil per day transited the "
                "Strait of Hormuz in 2018.",
                "load_bearing": True,
            },
            {
                "id": "p-strait-c2",
                "text": "Hormuz transit volume equalled roughly 21 percent of "
                "global consumption in 2018.",
                "load_bearing": False,
            },
        ),
        "paragraphs": (
            "From the Omani headland at Musandam in 2018 you could watch 21 million barrels of "
            "oil a day squeeze through a channel about 21 nautical miles wide, with the Strait "
            "of Hormuz carrying a fifth of the world's energy past a single lighthouse.",
            "That flow equalled roughly 21 percent of global consumption in 2018, and every "
            "tanker in it had been financed, insured, and scheduled long before it saw the Gulf.",
            "Which box, then, is really carrying the world?",
        ),
    },
}

FIXTURE_EDGES: tuple[dict, ...] = (
    {
        "from": "p-container",
        "to": "p-chip",
        "hook_angle": "The most expensive machine on earth still arrives in a box.",
        "rationale": (
            "The container cost collapse of 1956 is the same logistics system that now "
            "delivers ASML's $150 million machines to TSMC."
        ),
        "hook": "The most expensive machine on earth still arrives in a box — whose box?",
    },
    {
        "from": "p-chip",
        "to": "p-money",
        "hook_angle": "Who finances a $150 million machine before it sails?",
        "rationale": (
            "TSMC's $150 million tools are financed with the trade-credit instruments the "
            "ledger piece unpacks."
        ),
        "hook": "Who writes the cheque for a $150 million machine that hasn't sailed yet?",
    },
    {
        "from": "p-money",
        "to": "p-strait",
        "hook_angle": "A letter of credit is only as good as the water it crosses.",
        "rationale": (
            "The $9.6 billion a day pinned behind the Ever Given is exactly what the strait's "
            "chokepoint geography holds hostage."
        ),
        "hook": "What is a letter of credit worth when the canal is a parking lot?",
    },
    {
        "from": "p-strait",
        "to": "p-container",
        "hook_angle": "The strait's traffic is the box's traffic.",
        "rationale": (
            "Hormuz's tanker scheduling runs on the containerized logistics the 1956 Ideal-X "
            "sailing created."
        ),
        "hook": "How did a 1956 tanker conversion decide what fits through a strait?",
    },
    {
        "from": "p-container",
        "to": "p-money",
        "hook_angle": "Who owns a box mid-ocean?",
        "rationale": (
            "The 16-cent loading economics only work because letters of credit move faster "
            "than the boxes they finance."
        ),
        "hook": "Who actually owns the 58 boxes before they ever reach Houston?",
    },
)

TOPIC_BY_PIECE = {
    "p-container": "logistics",
    "p-chip": "semiconductors",
    "p-money": "financial-systems",
    "p-strait": "chokepoints",
}


def hub_url(piece_id: str) -> str:
    return f"https://hub.example/{piece_id}"


def primary_url(piece_id: str) -> str:
    return f"https://primary.example/{piece_id}"


def secondary_url(piece_id: str) -> str:
    return f"https://second.example/{piece_id}"


def fixture_web_source() -> FakeWebSource:
    """Canned pages: one hub per Piece whose cited links reach a primary and a secondary."""
    web = FakeWebSource()
    for piece_id, data in FIXTURE_PIECES.items():
        facts = " ".join(claim["text"] for claim in data["claims"])
        web.add(
            FetchedPage(
                url=hub_url(piece_id),
                content=f"Encyclopedia overview of {data['title']}. {facts}",
                outlinks=(primary_url(piece_id), secondary_url(piece_id)),
                fetched_at=FETCHED_AT,
            )
        )
        web.add(
            FetchedPage(
                url=primary_url(piece_id),
                content=f"Official record backing: {data['claims'][0]['text']}",
                outlinks=(),
                fetched_at=FETCHED_AT,
            )
        )
        web.add(
            FetchedPage(
                url=secondary_url(piece_id),
                content=f"Independent reporting on: {data['claims'][1]['text']}",
                outlinks=(),
                fetched_at=FETCHED_AT,
            )
        )
    return web


def _architect_plan(request: LLMRequest) -> str:
    topics = list(request.payload["target_topics"])
    concepts = []
    for index, piece_id in enumerate(PIECE_IDS):
        data = FIXTURE_PIECES[piece_id]
        concepts.append(
            {
                "id": piece_id,
                "title": data["title"],
                "premise": data["premise"],
                "topics": [topics[index % len(topics)]],
                "entry_worthy": piece_id == "p-container",
            }
        )
    edges = [
        {
            "from": edge["from"],
            "to": edge["to"],
            "hook_angle": edge["hook_angle"],
            "rationale": edge["rationale"],
        }
        for edge in FIXTURE_EDGES
    ]
    return json.dumps({"concepts": concepts, "connections": edges})


def _harvest(request: LLMRequest) -> str:
    piece_id = str(request.payload["piece_id"])
    claims = [
        {
            "id": claim["id"],
            "text": claim["text"],
            "load_bearing": claim["load_bearing"],
            "candidate_urls": [hub_url(piece_id)],
        }
        for claim in FIXTURE_PIECES[piece_id]["claims"]
    ]
    return json.dumps({"claims": claims})


KNOWN_CLAIM_IDS = frozenset(
    claim["id"] for data in FIXTURE_PIECES.values() for claim in data["claims"]
)


def _assess(request: LLMRequest) -> str:
    url = str(request.payload["url"])
    claims = [c for c in request.payload["claims"] if c["id"] in KNOWN_CLAIM_IDS]
    if url.startswith("https://hub."):
        tier, supports = "tertiary", [c["id"] for c in claims]
        credibility = "encyclopedia overview; useful map, tertiary authority"
    elif url.startswith("https://primary."):
        tier, supports = "primary", [claims[0]["id"]] if claims else []
        credibility = "official record; primary authority"
    else:
        tier, supports = "secondary", [c["id"] for c in claims[1:2]]
        credibility = "independent reporting; secondary authority"
    origin = url.split("/")[2]
    return json.dumps(
        {
            "tier": tier,
            "credibility": credibility,
            "origin_key": origin,
            "supports": [
                {"claim_id": claim_id, "excerpt": f"…{claim_id} supported…"}
                for claim_id in supports
            ],
        }
    )


def _refute(request: LLMRequest) -> str:
    return json.dumps({"verdict": "survived", "reason": "no contradiction found"})


def _draft(request: LLMRequest) -> str:
    piece_id = str(request.payload["piece_id"])
    data = FIXTURE_PIECES[piece_id]
    return json.dumps(
        {
            "title": data["title"],
            "teaser": data["teaser"],
            "read_time_min": 4,
            "blocks": [{"kind": "paragraph", "text": text} for text in data["paragraphs"]],
        }
    )


def _judge(request: LLMRequest) -> str:
    return json.dumps({"violations": []})


def _ground(request: LLMRequest) -> str:
    return json.dumps({"unsupported": []})


def _hook(request: LLMRequest) -> str:
    from_id = request.payload["from"]["id"]  # type: ignore[index]
    to_id = request.payload["to"]["id"]  # type: ignore[index]
    for edge in FIXTURE_EDGES:
        if edge["from"] == from_id and edge["to"] == to_id:
            return json.dumps({"hook": edge["hook"], "rationale": edge["rationale"]})
    return json.dumps(
        {
            "hook": f"What does {from_id} owe to {to_id} that neither will admit?",
            "rationale": f"The systems in {from_id} and {to_id} share one causal spine.",
        }
    )


def _tier2(request: LLMRequest) -> str:
    return json.dumps(
        {
            "judgements": [
                {"code": code, "passed": True, "note": "fixture pass"}
                for code in ("J1", "J2", "J3", "J4", "J5")
            ]
        }
    )


def well_behaved_llm() -> ScriptedLLM:
    """A scripted LLM whose every purpose emits well-formed fixture output."""
    return ScriptedLLM(
        {
            "architect.plan": _architect_plan,
            "researcher.harvest": _harvest,
            "researcher.assess": _assess,
            "researcher.refute": _refute,
            "writer.draft": _draft,
            "editor.judge": _judge,
            "editor.revise": _draft,
            "editor.ground": _ground,
            "editor.cut": _draft,
            "weaver.hook": _hook,
            "reviewer.tier2": _tier2,
        }
    )


def build_context(
    tmp_path: Path,
    llm: ScriptedLLM | None = None,
    web: FakeWebSource | None = None,
    repo: ContentGraphRepository | None = None,
    gates: GatePolicy | None = None,
    config: HarnessConfig | None = None,
    goal: str = FIXTURE_GOAL,
    run_id: str = "run-fixture",
) -> RunContext:
    """Assemble a RunContext over a temp workspace seeded with the fixture Brief."""
    workspace = RunWorkspace(tmp_path / run_id)
    if goal:
        workspace.write("goal.md", goal)
    specs = SpecLibrary(repo_root=REPO_ROOT)
    return RunContext(
        run_id=run_id,
        workspace=workspace,
        specs=specs,
        manifest=specs.manifest(),
        llm=llm or well_behaved_llm(),
        web=web or fixture_web_source(),
        repo=repo or InMemoryContentGraphRepository(),
        gates=gates or AutoApproveGates(),
        config=config or HarnessConfig(model="scripted-fake"),
    )

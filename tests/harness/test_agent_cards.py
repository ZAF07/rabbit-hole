"""Issue 10a — the roster splits into Claude Code subagent files (one spec, two runtimes)."""

from tests.harness.fixture_run import REPO_ROOT

from harness.runtimes.agent_cards import parse_agent_cards, render_subagent, write_agent_cards

ROSTER = (REPO_ROOT / "harness" / "agents" / "README.md").read_text()


def test_the_seven_agents_split_out_in_roster_order():
    cards = parse_agent_cards(ROSTER)
    assert [card.name for card in cards] == [
        "architect",
        "researcher",
        "writer",
        "editor",
        "weaver",
        "reviewer",
        "distiller",
    ]
    for card in cards:
        assert card.description
        assert "**Done when:**" in card.body


def test_tool_grants_come_from_the_card_not_a_hardcoded_map():
    cards = {card.name: card for card in parse_agent_cards(ROSTER)}
    assert cards["architect"].tools == ("ContentGraphRepository",)
    assert cards["researcher"].tools == ("WebSourcePort",)
    assert cards["writer"].tools == ()
    assert cards["editor"].tools == ()


def test_rendered_subagents_carry_frontmatter_and_the_verbatim_body():
    cards = {card.name: card for card in parse_agent_cards(ROSTER)}
    researcher = render_subagent(cards["researcher"])
    assert researcher.startswith("---\nname: researcher\n")
    assert "description: the closed-book substrate builder" in researcher
    assert "tools: WebSourcePort" in researcher
    assert "**2a Harvest**" in researcher

    writer = render_subagent(cards["writer"])
    assert "tools:" not in writer.split("---")[1]


def test_generation_is_deterministic(tmp_path):
    first = write_agent_cards(ROSTER, tmp_path / "a")
    second = write_agent_cards(ROSTER, tmp_path / "b")
    assert [p.name for p in first] == [p.name for p in second]
    for path_a, path_b in zip(first, second, strict=True):
        assert path_a.read_text() == path_b.read_text()


def test_committed_subagents_match_the_roster():
    for card in parse_agent_cards(ROSTER):
        committed = REPO_ROOT / ".claude" / "agents" / f"{card.name}.md"
        assert committed.is_file(), f"regenerate .claude/agents/ — missing {card.name}.md"
        assert committed.read_text() == render_subagent(card), (
            f".claude/agents/{card.name}.md drifted from harness/agents/README.md — regenerate"
        )

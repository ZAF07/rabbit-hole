"""The banned-filler list is data parsed from the guardrail spec, not code."""

from harness.guardrails.phrases import compile_phrase, find_banned, parse_banned_phrases

SPEC_SNIPPET = """
# Anti-Slop Guardrails

## Banned-filler phrases (check D3)
Some prose about the list.

- "In today's world" / "In an increasingly ___ world"
- "delve" / "a testament to"

## What this rubric does NOT judge
- "not a phrase" should not be parsed from here
"""


def test_parses_quoted_phrases_from_banned_section_only():
    phrases = parse_banned_phrases(SPEC_SNIPPET)
    assert "delve" in phrases
    assert "a testament to" in phrases
    assert "not a phrase" not in phrases


def test_real_spec_yields_a_substantial_list(banned_phrases):
    assert len(banned_phrases) >= 15
    assert "delve" in banned_phrases


def test_wildcard_phrase_matches_a_gap():
    pattern = compile_phrase("In an increasingly ___ world")
    assert pattern.search("in an increasingly digital world, nothing is offline")


def test_matching_is_case_insensitive():
    assert find_banned("It was a GAME-CHANGER for everyone.", ["game-changer"])


def test_find_banned_reports_each_phrase_once():
    text = "We delve, then delve again, a testament to persistence."
    assert find_banned(text, ["delve", "a testament to"]) == ("delve", "a testament to")

"""Shared fixtures for the harness test suite."""

from pathlib import Path

import pytest

from harness.guardrails.phrases import parse_banned_phrases

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def banned_phrases() -> tuple[str, ...]:
    """The real banned-filler list, parsed from the checked-in guardrail spec."""
    spec = (REPO_ROOT / "harness" / "guardrails" / "piece.md").read_text()
    return parse_banned_phrases(spec)

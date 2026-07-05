"""Guardrail evaluators — encoded taste as pure functions ``artifact → [violations]``.

The moat-bearing, exhaustively unit-testable core every stage consumes.
Deterministic and offline: no LLM call, no network, no disk. Checks that
require judgment (the reframe, clickbait, voice conformance) are listed as
judged checks for the machine-QA LLM judge; everything mechanical lives here
as binary FAIL-if rules — never "rate 1–10".
"""

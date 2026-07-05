"""The Reviewer's deliverable (``qa.md``) — Tier-1 results + Tier-2 judgements."""

from dataclasses import dataclass, field

from harness.domain.frontmatter import render_frontmatter, split_frontmatter
from harness.guardrails.constellation import TIER1_CODES, Tier1Report, Tier2Judgement


@dataclass(frozen=True)
class QAReport:
    """One run's constellation-QA outcome.

    Attributes:
        tier1: The binary I1–I8 report.
        tier2: The Reviewer's J1–J5 judgements.
        escalations: Tier-2 flags escalated to the human queue rather than
            resolved by a loop.
    """

    tier1: Tier1Report
    tier2: tuple[Tier2Judgement, ...] = ()
    escalations: tuple[str, ...] = field(default_factory=tuple)


def render_qa_report(report: QAReport) -> str:
    """Serialize a QA report to ``qa.md`` text.

    Args:
        report: The report to serialize.

    Returns:
        The deliverable text.
    """
    fields: dict[str, str | int | bool | list[str]] = {
        "tier1_pass": report.tier1.passed,
        "escalations": list(report.escalations),
    }
    lines = ["## Tier 1 — outcome contract", ""]
    for code in TIER1_CODES:
        verdict = "pass" if report.tier1.results.get(code, False) else "FAIL"
        lines.append(f"- {code}: {verdict}")
    if report.tier1.violations:
        lines.extend(["", "### Violations", ""])
        lines.extend(
            f"- {violation.code} · {violation.subject} · {violation.message}"
            for violation in report.tier1.violations
        )
    lines.extend(["", "## Tier 2 — journey coherence", ""])
    for judgement in report.tier2:
        verdict = "pass" if judgement.passed else "FLAG"
        note = f" — {judgement.note}" if judgement.note else ""
        lines.append(f"- {judgement.code}: {verdict}{note}")
    return render_frontmatter(fields, "\n".join(lines))


def parse_qa_outcome(text: str) -> tuple[bool, tuple[str, ...]]:
    """Read the QA outcome a later step gates on.

    Args:
        text: The ``qa.md`` text.

    Returns:
        (tier1 passed, escalated Tier-2 codes).
    """
    fields, _ = split_frontmatter(text)
    passed = fields.get("tier1_pass") == "true"
    escalations = fields.get("escalations", [])
    return passed, tuple(escalations) if isinstance(escalations, list) else (str(escalations),)

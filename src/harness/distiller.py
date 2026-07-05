"""The Distiller — the batched, human-ratified learning loop (ADR 0004).

Out-of-band, never a pipeline stage: it reads the verdict corpus accumulated
across runs (``feedback/verdicts.jsonl`` + edit-diffs) and *proposes*
improvements to the taste artifacts — banned-phrase additions from phrases
the human repeatedly deleted, new checks from repeated reject reasons, and
per-Topic machine-vs-human agreement counts so gate relaxation can later be
data-gated per Topic. Nothing here auto-merges: a proposal is inert markdown
until :func:`apply_proposal` is explicitly called on a human-ratified one.
"""

import difflib
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from harness.domain.verdicts import VerdictRecord, parse_verdict_line
from harness.errors import MalformedArtifactError
from harness.guardrails.phrases import compile_phrase, parse_banned_phrases

_BANNED_HEADING = "## Banned-filler phrases"
_WORD = re.compile(r"[a-z0-9'’-]+")
_NGRAM_MIN = 2
_NGRAM_MAX = 6
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "for",
        "from",
        "her",
        "his",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "their",
        "this",
        "to",
        "was",
        "were",
        "with",
    }
)


@dataclass(frozen=True)
class ProposedCheck:
    """A candidate new guardrail check distilled from repeated rejections.

    Attributes:
        reason: The normalized human reject reason.
        count: How many verdicts carried it.
        gates: The gates the rejections came from, sorted.
    """

    reason: str
    count: int
    gates: tuple[str, ...]


@dataclass(frozen=True)
class TopicAgreement:
    """Machine-vs-human agreement for one Topic.

    A plain approve counts as agreement; an edit-approve or reject counts as
    disagreement — the human had to intervene.

    Attributes:
        topic_id: The Topic.
        agree: Verdicts where the machine's output stood as-is.
        disagree: Verdicts where the human edited or rejected.
    """

    topic_id: str
    agree: int
    disagree: int

    def total(self) -> int:
        """Total verdicts observed for the Topic.

        Returns:
            agree + disagree.
        """
        return self.agree + self.disagree

    def agreement_rate(self) -> float:
        """Fraction of verdicts where the machine's output stood.

        Returns:
            agree / total, or 0.0 with no observations.
        """
        return self.agree / self.total() if self.total() else 0.0


@dataclass(frozen=True)
class Proposal:
    """One batch's distilled, not-yet-ratified improvement proposal.

    Attributes:
        banned_phrase_additions: Phrases the human deleted in at least the
            threshold number of verdicts, absent from the current list.
        proposed_checks: Reject reasons recurring at or above the threshold.
        topic_agreement: Per-Topic agreement counts, sorted by Topic id.
    """

    banned_phrase_additions: tuple[str, ...]
    proposed_checks: tuple[ProposedCheck, ...]
    topic_agreement: tuple[TopicAgreement, ...]

    def is_empty(self) -> bool:
        """Whether the batch surfaced nothing actionable.

        Returns:
            True if there are no additions and no proposed checks.
        """
        return not self.banned_phrase_additions and not self.proposed_checks


def load_corpus(paths: Sequence[Path]) -> tuple[VerdictRecord, ...]:
    """Read the verdict corpus from one or more runs' verdict logs.

    Args:
        paths: ``feedback/verdicts.jsonl`` paths, one per run.

    Returns:
        Every record, in file order then line order.
    """
    records: list[VerdictRecord] = []
    for path in paths:
        for line in Path(path).read_text().splitlines():
            if line.strip():
                records.append(parse_verdict_line(line))
    return tuple(records)


def _diff_removed_and_added(diff: str) -> tuple[str, str]:
    """Split a unified diff into its removed and added line texts.

    Args:
        diff: The unified machine→human diff.

    Returns:
        (removed text, added text), header lines excluded.
    """
    removed: list[str] = []
    added: list[str] = []
    for line in diff.splitlines():
        if line.startswith(("---", "+++")):
            continue
        if line.startswith("-"):
            removed.append(line[1:])
        elif line.startswith("+"):
            added.append(line[1:])
    return "\n".join(removed), "\n".join(added)


def _ngrams(text: str) -> frozenset[str]:
    """Collect the candidate word n-grams present in a text.

    Line-scoped so a gram never spans two deleted lines; grams made purely
    of stopwords are dropped as unproposable noise.

    Args:
        text: The text to scan.

    Returns:
        The distinct n-grams, casefolded.
    """
    grams: set[str] = set()
    for line in text.splitlines():
        words = _WORD.findall(line.casefold())
        for size in range(_NGRAM_MIN, _NGRAM_MAX + 1):
            for start in range(len(words) - size + 1):
                window = words[start : start + size]
                if any(word not in _STOPWORDS for word in window):
                    grams.add(" ".join(window))
    return frozenset(grams)


def _propose_banned_phrases(
    corpus: Sequence[VerdictRecord], current_banned: Sequence[str], threshold: int
) -> tuple[str, ...]:
    """Find phrases the human deleted in enough distinct verdicts.

    A gram counts once per verdict, only when it appears in that diff's
    removed lines and not its added lines (deleted, not merely moved).
    Spans matching an already-banned phrase are stripped first so nothing
    the list covers is re-proposed; grams contained in an already-kept
    longer candidate are folded away.

    Args:
        corpus: The verdict corpus.
        current_banned: The phrases already in the list.
        threshold: Minimum number of distinct verdicts.

    Returns:
        The proposed additions, strongest (most seen, then longest) first.
    """
    patterns = [compile_phrase(phrase) for phrase in current_banned]

    def strip_known(text: str) -> str:
        for pattern in patterns:
            text = pattern.sub(" ", text)
        return text

    counts: Counter[str] = Counter()
    for record in corpus:
        if not record.edit_diff:
            continue
        removed, added = _diff_removed_and_added(record.edit_diff)
        counts.update(_ngrams(strip_known(removed)) - _ngrams(strip_known(added)))
    candidates = [gram for gram, seen in counts.items() if seen >= threshold]
    kept: list[str] = []
    for gram in sorted(candidates, key=lambda g: (-counts[g], -len(g), g)):
        if not any(gram in longer for longer in kept):
            kept.append(gram)
    return tuple(kept)


def _normalize_reason(reason: str) -> str:
    """Collapse a reject reason to its comparison form.

    Args:
        reason: The human's reason as recorded.

    Returns:
        Casefolded, whitespace-collapsed, trailing punctuation stripped.
    """
    return " ".join(reason.split()).casefold().rstrip(".!")


def _propose_checks(corpus: Sequence[VerdictRecord], threshold: int) -> tuple[ProposedCheck, ...]:
    """Find reject reasons that recur across the corpus.

    Args:
        corpus: The verdict corpus.
        threshold: Minimum number of rejects sharing a reason.

    Returns:
        One proposed check per recurring reason, most seen first.
    """
    groups: dict[str, list[VerdictRecord]] = {}
    for record in corpus:
        if record.verdict != "reject" or not record.reason.strip():
            continue
        groups.setdefault(_normalize_reason(record.reason), []).append(record)
    proposals = [
        ProposedCheck(
            reason=reason,
            count=len(records),
            gates=tuple(sorted({record.gate for record in records})),
        )
        for reason, records in groups.items()
        if len(records) >= threshold
    ]
    return tuple(sorted(proposals, key=lambda check: (-check.count, check.reason)))


def compute_topic_agreement(corpus: Sequence[VerdictRecord]) -> tuple[TopicAgreement, ...]:
    """Count machine-vs-human agreement per Topic across the corpus.

    Args:
        corpus: The verdict corpus.

    Returns:
        One entry per Topic seen, sorted by Topic id.
    """
    agree: Counter[str] = Counter()
    disagree: Counter[str] = Counter()
    for record in corpus:
        bucket = agree if record.verdict == "approve" else disagree
        for topic in record.topics:
            bucket[topic] += 1
    return tuple(
        TopicAgreement(topic_id=topic, agree=agree[topic], disagree=disagree[topic])
        for topic in sorted(set(agree) | set(disagree))
    )


def distill(
    corpus: Sequence[VerdictRecord], piece_guardrail_text: str, threshold: int = 2
) -> Proposal:
    """Distill one batch of verdicts into an improvement proposal.

    Args:
        corpus: The verdict corpus (see :func:`load_corpus`).
        piece_guardrail_text: The current ``harness/guardrails/piece.md``
            text, for the already-banned list.
        threshold: Minimum recurrences before something is proposed.

    Returns:
        The proposal — inert until ratified and applied.
    """
    current = parse_banned_phrases(piece_guardrail_text)
    return Proposal(
        banned_phrase_additions=_propose_banned_phrases(corpus, current, threshold),
        proposed_checks=_propose_checks(corpus, threshold),
        topic_agreement=compute_topic_agreement(corpus),
    )


def _insert_banned_phrases(markdown: str, phrases: Sequence[str]) -> str:
    """Insert new phrases at the end of the banned-list section.

    Args:
        markdown: The current guardrail file text.
        phrases: The ratified additions.

    Returns:
        The updated text.

    Raises:
        MalformedArtifactError: If the banned-phrases section is missing.
    """
    lines = markdown.splitlines(keepends=True)
    in_section = False
    last_item = -1
    for index, line in enumerate(lines):
        if line.startswith("## "):
            in_section = line.startswith(_BANNED_HEADING)
            continue
        if in_section and line.lstrip().startswith("- "):
            last_item = index
    if last_item < 0:
        raise MalformedArtifactError(f"no {_BANNED_HEADING!r} list to extend")
    additions = [f'- "{phrase}"\n' for phrase in phrases]
    return "".join(lines[: last_item + 1] + additions + lines[last_item + 1 :])


def render_proposal(proposal: Proposal, piece_guardrail_text: str) -> str:
    """Render a proposal as the markdown the human ratifies against.

    The banned-phrase section is presented as a unified diff of the
    guardrail file — what *would* change, not what has.

    Args:
        proposal: The distilled proposal.
        piece_guardrail_text: The current guardrail file text.

    Returns:
        The proposal document.
    """
    parts = ["# Distiller proposal — nothing below is applied until ratified", ""]
    parts.append("## Proposed banned-phrase additions")
    if proposal.banned_phrase_additions:
        updated = _insert_banned_phrases(piece_guardrail_text, proposal.banned_phrase_additions)
        diff = difflib.unified_diff(
            piece_guardrail_text.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile="harness/guardrails/piece.md (current)",
            tofile="harness/guardrails/piece.md (proposed)",
        )
        parts.extend(["", "```diff", "".join(diff).rstrip("\n"), "```"])
    else:
        parts.extend(["", "*None this batch.*"])
    parts.extend(["", "## Proposed new checks (from repeated reject reasons)"])
    if proposal.proposed_checks:
        parts.append("")
        parts.extend(
            f"- seen {check.count}× at gate(s) {', '.join(check.gates)}: “{check.reason}”"
            for check in proposal.proposed_checks
        )
    else:
        parts.extend(["", "*None this batch.*"])
    parts.extend(["", "## Per-Topic machine-vs-human agreement", ""])
    if proposal.topic_agreement:
        parts.extend(
            f"- {entry.topic_id}: {entry.agree} agree / {entry.disagree} disagree "
            f"({entry.agreement_rate():.0%})"
            for entry in proposal.topic_agreement
        )
    else:
        parts.append("*No Topic signal in this batch.*")
    return "\n".join(parts) + "\n"


def apply_proposal(proposal: Proposal, piece_guardrail_path: Path) -> None:
    """Apply a human-ratified proposal — the only mutator in the loop.

    Only the mechanical part (banned-phrase additions) is applied; proposed
    checks are prose for the human to work into the specs by hand.

    Args:
        proposal: The ratified proposal.
        piece_guardrail_path: Path to ``harness/guardrails/piece.md``.
    """
    if not proposal.banned_phrase_additions:
        return
    text = piece_guardrail_path.read_text()
    piece_guardrail_path.write_text(_insert_banned_phrases(text, proposal.banned_phrase_additions))

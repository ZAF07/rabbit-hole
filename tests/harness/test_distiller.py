"""Issue 09 — the Distiller: batched, human-ratified learning loop (ADR 0004)."""

import shutil

from tests.harness.fixture_run import REPO_ROOT

from harness.distiller import (
    apply_proposal,
    compute_topic_agreement,
    distill,
    load_corpus,
    render_proposal,
)
from harness.domain.verdicts import VerdictRecord
from harness.guardrails.phrases import find_banned, parse_banned_phrases

GUARDRAIL_TEXT = (REPO_ROOT / "harness" / "guardrails" / "piece.md").read_text()


def verdict(gate="piece", target_id="p-x", value="approve", reason="", diff=None, topics=()):
    return VerdictRecord(
        ts="2026-07-05T00:00:00+00:00",
        run_id="run-a",
        runtime="langgraph",
        model="scripted-fake",
        gate=gate,
        target_id=target_id,
        verdict=value,
        reason=reason,
        edit_diff=diff,
        topics=tuple(topics),
    )


def deletion_diff(removed, added):
    return (
        "--- pieces/p-x/piece.md (machine)\n"
        "+++ pieces/p-x/piece.md (human)\n"
        "@@ -1,1 +1,1 @@\n"
        f"-{removed}\n"
        f"+{added}\n"
    )


def test_repeated_deletions_propose_a_banned_phrase_as_a_diff_not_a_change(tmp_path):
    corpus = (
        verdict(
            value="edit_approve",
            diff=deletion_diff(
                "It was a perfect storm of delays at the port.",
                "Delays stacked up at the port.",
            ),
        ),
        verdict(
            value="edit_approve",
            diff=deletion_diff(
                "The strike created a perfect storm for shippers.",
                "The strike stranded the shippers.",
            ),
        ),
    )
    proposal = distill(corpus, GUARDRAIL_TEXT)
    assert "a perfect storm" in proposal.banned_phrase_additions

    rendered = render_proposal(proposal, GUARDRAIL_TEXT)
    assert '+- "a perfect storm"' in rendered
    assert "nothing below is applied until ratified" in rendered
    assert "a perfect storm" not in parse_banned_phrases(GUARDRAIL_TEXT)


def test_a_phrase_deleted_in_only_one_verdict_is_not_proposed():
    corpus = (
        verdict(
            value="edit_approve",
            diff=deletion_diff(
                "It was a perfect storm of delays at the port.",
                "Delays stacked up at the port.",
            ),
        ),
    )
    proposal = distill(corpus, GUARDRAIL_TEXT)
    assert "a perfect storm" not in proposal.banned_phrase_additions


def test_already_banned_phrases_are_not_reproposed():
    corpus = tuple(
        verdict(
            value="edit_approve",
            diff=deletion_diff(
                f"At the end of the day the port survived round {index}.",
                "The port survived.",
            ),
        )
        for index in range(3)
    )
    proposal = distill(corpus, GUARDRAIL_TEXT)
    assert not any("end of the day" in phrase for phrase in proposal.banned_phrase_additions)


def test_repeated_reject_reasons_propose_a_new_check():
    rehash = "Premise is a rehash of an existing piece."
    corpus = (
        verdict(target_id="p-a", value="reject", reason=rehash),
        verdict(target_id="p-b", value="reject", reason=rehash.lower().rstrip(".")),
        verdict(target_id="p-c", value="reject", reason="Hook overpromises the destination."),
    )
    proposal = distill(corpus, GUARDRAIL_TEXT)
    assert len(proposal.proposed_checks) == 1
    check = proposal.proposed_checks[0]
    assert check.reason == "premise is a rehash of an existing piece"
    assert check.count == 2
    assert check.gates == ("piece",)
    assert "premise is a rehash" in render_proposal(proposal, GUARDRAIL_TEXT)


def test_per_topic_agreement_counts_come_from_the_verdict_corpus():
    corpus = (
        verdict(value="approve", topics=("logistics",)),
        verdict(value="approve", topics=("logistics", "chokepoints")),
        verdict(value="edit_approve", diff=None, topics=("logistics",)),
        verdict(value="reject", reason="flat", topics=("chokepoints",)),
    )
    agreement = {entry.topic_id: entry for entry in compute_topic_agreement(corpus)}
    assert agreement["logistics"].agree == 2
    assert agreement["logistics"].disagree == 1
    assert agreement["chokepoints"].agree == 1
    assert agreement["chokepoints"].disagree == 1
    assert agreement["logistics"].agreement_rate() == 2 / 3


def test_nothing_mutates_until_the_proposal_is_explicitly_applied(tmp_path):
    guardrail = tmp_path / "piece.md"
    shutil.copy(REPO_ROOT / "harness" / "guardrails" / "piece.md", guardrail)
    before = guardrail.read_text()

    corpus = (
        verdict(
            value="edit_approve",
            diff=deletion_diff("A perfect storm hit the docks.", "The docks flooded."),
        ),
        verdict(
            value="edit_approve",
            diff=deletion_diff("It became a perfect storm at sea.", "It worsened at sea."),
        ),
    )
    proposal = distill(corpus, before)
    render_proposal(proposal, before)
    assert guardrail.read_text() == before

    apply_proposal(proposal, guardrail)
    updated = parse_banned_phrases(guardrail.read_text())
    assert "a perfect storm" in updated
    assert find_banned("Frankly, it was a perfect storm.", updated) == ("a perfect storm",)


def test_load_corpus_spans_multiple_runs(tmp_path):
    log_a = tmp_path / "run-a" / "verdicts.jsonl"
    log_b = tmp_path / "run-b" / "verdicts.jsonl"
    log_a.parent.mkdir()
    log_b.parent.mkdir()
    log_a.write_text(verdict(target_id="p-a").to_json_line())
    log_b.write_text(
        verdict(target_id="p-b").to_json_line()
        + verdict(target_id="p-c", value="reject", reason="flat").to_json_line()
    )
    corpus = load_corpus([log_a, log_b])
    assert [record.target_id for record in corpus] == ["p-a", "p-b", "p-c"]

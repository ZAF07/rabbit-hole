"""Issue 04 — the closed-book Researcher: recall-first, citation-chasing, the bar."""

import dataclasses
import json

import pytest
from tests.harness.fixture_run import (
    FIXTURE_PIECES,
    build_context,
    fixture_web_source,
    hub_url,
    primary_url,
    secondary_url,
)

from harness.adapters.fakes import FakeWebSource
from harness.domain.grounding import ClaimStatus, SourceTier
from harness.domain.grounding_io import ledger_from_json
from harness.errors import ThinSourcePackError
from harness.pipeline import stages
from harness.pipeline.context import HarnessConfig
from harness.ports.web_source import WebSourcePort


def run_source(ctx):
    stages.run_stage_plan(ctx)
    stages.run_stage_source(ctx)


def ledger_for(ctx, piece_id):
    return ledger_from_json(ctx.workspace.read(stages.grounding_path(piece_id)))


def test_port_surface_has_no_search_query():
    assert not hasattr(WebSourcePort, "search")
    port_methods = {
        name
        for name in dir(WebSourcePort)
        if not name.startswith("_") and callable(getattr(WebSourcePort, name))
    }
    assert port_methods == {"fetch"}


def test_primary_source_reached_by_following_hub_cited_link(tmp_path):
    from tests.harness.fixture_run import _harvest

    ctx = build_context(tmp_path)
    run_source(ctx)
    assert hub_url("p-container") in ctx.web.fetched
    assert primary_url("p-container") in ctx.web.fetched
    harvest_requests = [r for r in ctx.llm.requests if r.purpose == "researcher.harvest"]
    recalled = {
        url
        for request in harvest_requests
        for claim in json.loads(_harvest(request))["claims"]
        for url in claim["candidate_urls"]
    }
    assert primary_url("p-container") not in recalled
    assert all(url.startswith("https://hub.") for url in recalled)


def test_single_primary_source_claim_survives_alone(tmp_path):
    ctx = build_context(tmp_path)
    run_source(ctx)
    ledger = ledger_for(ctx, "p-container")
    claim = next(c for c in ledger.claims if c.id == "p-container-c1")
    assert claim.status is ClaimStatus.VERIFIED
    assert claim.tier is SourceTier.PRIMARY


def test_claim_without_second_independent_source_is_cut_not_shipped(tmp_path):
    web = fixture_web_source()
    web._pages = {
        url: page for url, page in web._pages.items() if not url.startswith("https://second.")
    }
    config = HarnessConfig(min_verified_claims=1)
    ctx = build_context(tmp_path, web=web, config=config)
    run_source(ctx)
    ledger = ledger_for(ctx, "p-container")
    cut = next(c for c in ledger.claims if c.id == "p-container-c2")
    assert cut.status is ClaimStatus.DROPPED
    kept = next(c for c in ledger.claims if c.id == "p-container-c1")
    assert kept.status is ClaimStatus.VERIFIED


def test_internal_only_claim_is_dropped_and_recorded_never_silently_kept(tmp_path):
    ctx = build_context(tmp_path)

    def harvest_with_internal(request):
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
        claims.append(
            {
                "id": f"{piece_id}-c9",
                "text": "A striking fact the model merely remembers.",
                "load_bearing": False,
                "candidate_urls": [],
            }
        )
        return json.dumps({"claims": claims})

    ctx.llm.on("researcher.harvest", harvest_with_internal)
    run_source(ctx)
    ledger = ledger_for(ctx, "p-container")
    internal = next(c for c in ledger.claims if c.id == "p-container-c9")
    assert internal.status is ClaimStatus.DROPPED
    assert internal.internal_only is True


def test_load_bearing_internal_only_claim_is_flagged_to_the_human(tmp_path):
    ctx = build_context(tmp_path)

    def harvest_with_flagged(request):
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
        claims.append(
            {
                "id": f"{piece_id}-c9",
                "text": "The premise hangs on this unsourced memory.",
                "load_bearing": True,
                "candidate_urls": [],
            }
        )
        return json.dumps({"claims": claims})

    ctx.llm.on("researcher.harvest", harvest_with_flagged)
    run_source(ctx)
    ledger = ledger_for(ctx, "p-container")
    flagged = next(c for c in ledger.claims if c.id == "p-container-c9")
    assert flagged.status is ClaimStatus.FLAGGED


def test_thin_source_pack_fails_before_the_writer_runs(tmp_path):
    ctx = build_context(tmp_path, web=FakeWebSource())
    stages.run_stage_plan(ctx)
    with pytest.raises(ThinSourcePackError, match="dies at research"):
        stages.run_stage_source(ctx)
    assert not ctx.workspace.exists(stages.draft_path("p-container"))
    assert all(r.purpose != "writer.draft" for r in ctx.llm.requests)


def test_refuted_claim_is_dropped_with_verdict_recorded(tmp_path):
    ctx = build_context(tmp_path)
    original_refute = ctx.llm._handlers["researcher.refute"]

    def refute_c2(request):
        if "16 cents" in str(request.payload["claim"]):
            return json.dumps({"verdict": "refuted", "reason": "numbers conflict"})
        return original_refute(request)

    ctx.llm.on("researcher.refute", refute_c2)
    config = HarnessConfig(min_verified_claims=1)
    ctx = dataclasses.replace(ctx, config=config)
    run_source(ctx)
    ledger = ledger_for(ctx, "p-container")
    refuted = next(c for c in ledger.claims if c.id == "p-container-c2")
    assert refuted.status is ClaimStatus.DROPPED
    assert str(refuted.refutation) == "refuted"


def test_ledger_records_claim_tier_status_sources_and_refutation(tmp_path):
    ctx = build_context(tmp_path)
    run_source(ctx)
    ledger = ledger_for(ctx, "p-chip")
    assert ledger.piece_id == "p-chip"
    verified = ledger.verified_claims()
    assert verified
    for claim in verified:
        assert claim.tier in tuple(SourceTier)
        assert claim.sources
        assert str(claim.refutation) == "survived"
        for source in claim.sources:
            assert source.citation.startswith("https://")
            assert source.tier in tuple(SourceTier)
            assert source.retrieved_at


def test_fetched_content_is_snapshotted_per_run(tmp_path):
    ctx = build_context(tmp_path)
    run_source(ctx)
    snapshots = list((ctx.workspace.root / "pieces" / "p-container" / "snapshots").iterdir())
    assert len(snapshots) == 3
    assert any("hub-example" in snapshot.name for snapshot in snapshots)


def test_citation_chasing_respects_the_per_page_limit(tmp_path):
    web = fixture_web_source()
    config = HarnessConfig(citation_limit=1, min_verified_claims=1)
    ctx = build_context(tmp_path, web=web, config=config)
    run_source(ctx)
    assert primary_url("p-container") in web.fetched
    assert secondary_url("p-container") not in web.fetched


def test_secondary_claim_verified_by_two_independent_origins(tmp_path):
    ctx = build_context(tmp_path)
    run_source(ctx)
    ledger = ledger_for(ctx, "p-money")
    claim = next(c for c in ledger.claims if c.id == "p-money-c2")
    assert claim.status is ClaimStatus.VERIFIED
    origins = {source.independence_key() for source in claim.sources}
    assert len(origins) >= 2

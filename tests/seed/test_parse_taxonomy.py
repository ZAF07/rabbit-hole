"""Unit tests for parsing the seed taxonomy out of docs/taxonomy.md."""

from pathlib import Path

from content_graph.seed import parse_seed_taxonomy, slugify

TAXONOMY_MD = (Path(__file__).parents[2] / "docs" / "taxonomy.md").read_text(encoding="utf-8")


def test_slugify_handles_ampersands_apostrophes_and_slashes() -> None:
    assert slugify("Engineering & Infrastructure") == "engineering-and-infrastructure"
    assert slugify("The Internet's Plumbing") == "the-internets-plumbing"
    assert slugify("AI/ML") == "ai-ml"


def test_parses_the_five_v1_categories_and_their_subcategories() -> None:
    seed = parse_seed_taxonomy(TAXONOMY_MD)
    by_id = {topic.id: topic for topic in seed.topics}

    categories = [tid for tid, parents in seed.parents.items() if not parents]
    assert "engineering-and-infrastructure" in categories
    assert "technology-and-computing" in categories

    assert seed.parents["logistics-and-supply-chains"] == {"engineering-and-infrastructure"}
    assert seed.parents["semiconductors"] == {"technology-and-computing"}
    assert by_id["ai-ml"].title == "AI/ML"


def test_multi_parent_examples_produce_multi_parent_topics() -> None:
    seed = parse_seed_taxonomy(TAXONOMY_MD)

    assert seed.parents["behavioral-economics"] == {
        "economics-and-markets",
        "psychology-and-the-mind",
    }
    assert seed.parents["cyber-conflict"] == {
        "technology-and-computing",
        "warfare-and-strategy",
    }
    assert "psychology-and-the-mind" in {topic.id for topic in seed.topics}

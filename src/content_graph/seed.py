"""Load the V1 seed Topic taxonomy (docs/taxonomy.md) through the write surface.

The seed is parsed from the design record itself so the stored taxonomy and
the documented one cannot drift. Parsing recognizes two shapes:

- The V1 cluster table — ``| **Category** | Sub · Sub · Sub |`` rows become a
  parent Topic and its children.
- The multi-parent examples list — ``- **Child** → *Parent* + *Parent*``
  bullets add the extra parents that make the DAG a DAG; a parent from a
  deferred wave is created as a Topic so the DAG is stored faithfully.
"""

import re
from dataclasses import dataclass

from content_graph.domain.topic import Topic
from content_graph.ports.repository import ContentGraphRepository

_TABLE_ROW = re.compile(r"^\|\s*\*\*(?P<category>[^*]+)\*\*\s*\|(?P<subcategories>[^|]+)\|")
_MULTI_PARENT_BULLET = re.compile(r"^-\s+\*\*(?P<child>[^*]+)\*\*\s*→(?P<parents>.+)$")


def slugify(title: str) -> str:
    """Derive a URL-safe Topic slug (and id) from its display title.

    Args:
        title: The display title, e.g. ``"Engineering & Infrastructure"``.

    Returns:
        The slug, e.g. ``"engineering-and-infrastructure"``.
    """
    text = title.lower().replace("&", " and ").replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


@dataclass(frozen=True)
class SeedTaxonomy:
    """The parsed seed: every Topic plus each Topic's parent-id set.

    Attributes:
        topics: All Topics in the seed, root and nested alike.
        parents: Topic id -> the ids of its parents (empty set for roots).
    """

    topics: tuple[Topic, ...]
    parents: dict[str, set[str]]


def parse_seed_taxonomy(markdown: str) -> SeedTaxonomy:
    """Parse the seed taxonomy out of the taxonomy design doc.

    Args:
        markdown: The full text of ``docs/taxonomy.md``.

    Returns:
        The Topics and the multi-parent DAG they form.
    """
    topics: dict[str, Topic] = {}
    parents: dict[str, set[str]] = {}

    def ensure_topic(title: str) -> str:
        """Register the Topic for a title if new; return its id.

        Args:
            title: The Topic's display title as written in the doc.

        Returns:
            The Topic's id (its slug).
        """
        slug = slugify(title)
        topics.setdefault(slug, Topic(id=slug, slug=slug, title=title.strip()))
        parents.setdefault(slug, set())
        return slug

    for line in markdown.splitlines():
        row = _TABLE_ROW.match(line.strip())
        if row:
            parent_id = ensure_topic(row.group("category"))
            for child_title in row.group("subcategories").split("·"):
                if child_title.strip():
                    parents[ensure_topic(child_title)].add(parent_id)
            continue
        bullet = _MULTI_PARENT_BULLET.match(line.strip())
        if bullet:
            child_id = ensure_topic(bullet.group("child"))
            for parent in bullet.group("parents").split("+"):
                title = parent.strip().strip("*").strip()
                if title:
                    parents[child_id].add(ensure_topic(title))

    return SeedTaxonomy(topics=tuple(topics.values()), parents=parents)


def load_seed_taxonomy(repo: ContentGraphRepository, markdown: str) -> tuple[Topic, ...]:
    """Write the parsed seed taxonomy into the store; idempotent end to end.

    Args:
        repo: The repository to write through.
        markdown: The full text of ``docs/taxonomy.md``.

    Returns:
        The Topics that were upserted.
    """
    seed = parse_seed_taxonomy(markdown)
    for topic in seed.topics:
        repo.upsert_topic(topic)
    for topic_id, parent_ids in seed.parents.items():
        repo.set_topic_parents(topic_id, sorted(parent_ids))
    return seed.topics

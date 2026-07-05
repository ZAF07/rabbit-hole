"""Topic — a node in the content classification taxonomy.

Topics form a shallow multi-parent DAG: a Topic may have zero or more parent
Topics, and a strict single-parent tree is explicitly rejected (ADR 0002).
Topics classify content; they never constrain Connections.
"""

from dataclasses import dataclass

from content_graph.domain.errors import TopicValidationError
from content_graph.domain.validation import require_non_empty_strings


@dataclass(frozen=True)
class Topic:
    """A taxonomy node, written by generation.

    Attributes:
        id: Caller-supplied identity; upserts are idempotent by this id.
        slug: URL-safe unique name.
        title: Display title.
    """

    id: str
    slug: str
    title: str

    def __post_init__(self) -> None:
        """Validate that identity and naming fields are non-empty.

        Raises:
            TopicValidationError: If id, slug, or title is blank.
        """
        require_non_empty_strings(self, ("id", "slug", "title"), TopicValidationError)

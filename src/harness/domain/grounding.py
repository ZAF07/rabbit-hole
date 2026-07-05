"""The grounding ledger — the closed-book audit trail of ADR 0005.

Per Piece, the ledger records every candidate claim's journey through the
Stage-2 sub-pipeline (Harvest → Vet → Corroborate → Refute): its tier, its
status, the sources that back it, and the refutation verdict. Persisted
regardless of display, so any shipped fact is inspectable and a wrong one is
traceable to its exact source and round.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum


class SourceTier(StrEnum):
    """How close a source sits to the fact itself (guardrails/sourcing.md)."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"


class ClaimStatus(StrEnum):
    """A claim's admission outcome against the corroboration bar."""

    VERIFIED = "verified"
    DROPPED = "dropped"
    FLAGGED = "flagged"


class RefutationVerdict(StrEnum):
    """The outcome of the 2d adversarial red-team round for one claim."""

    SURVIVED = "survived"
    REFUTED = "refuted"


@dataclass(frozen=True)
class SourceRecord:
    """One vetted source backing a claim.

    Attributes:
        citation: URL or bibliographic reference.
        tier: The source's tier per guardrails/sourcing.md.
        credibility: Why it passed the 2b vet (authority, recency, bias).
        excerpt: The supporting excerpt retrieved from the source.
        retrieved_at: ISO timestamp of retrieval (empty for offline sources).
        origin_key: Identity used to collapse wire/echo repeats when counting
            independent sources; defaults to the citation itself.
    """

    citation: str
    tier: SourceTier
    credibility: str = ""
    excerpt: str = ""
    retrieved_at: str = ""
    origin_key: str = ""

    def independence_key(self) -> str:
        """Return the key under which this source counts as one origin.

        Returns:
            The explicit origin key when set, otherwise the citation.
        """
        return self.origin_key or self.citation


@dataclass(frozen=True)
class ClaimRecord:
    """One atomic claim's full ledger entry.

    Attributes:
        id: Stable claim identity within its Piece.
        text: The claim, stated atomically.
        tier: The best tier among the claim's backing sources; ``TERTIARY``
            for internal-only claims that never found a source.
        status: The admission outcome (verified / dropped / flagged).
        sources: The vetted sources backing the claim.
        refutation: The 2d red-team verdict; None if the round never ran.
        load_bearing: True if the Piece's premise depends on this claim —
            an unverified load-bearing claim is flagged to the human, and a
            constellation shipping one fails I8.
        internal_only: True if the claim came from model recall and no
            external source was found for it.
    """

    id: str
    text: str
    tier: SourceTier
    status: ClaimStatus
    sources: tuple[SourceRecord, ...] = ()
    refutation: RefutationVerdict | None = None
    load_bearing: bool = False
    internal_only: bool = False

    def __post_init__(self) -> None:
        """Normalize the source list to a tuple."""
        object.__setattr__(self, "sources", tuple(self.sources))


@dataclass(frozen=True)
class GroundingLedger:
    """The per-Piece grounding record (``pieces/<id>/grounding.json``).

    Attributes:
        piece_id: The Piece this ledger grounds.
        claims: Every candidate claim's ledger entry — verified, dropped,
            and flagged alike; the audit trail keeps them all.
    """

    piece_id: str
    claims: Sequence[ClaimRecord] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Normalize the claim list to a tuple."""
        object.__setattr__(self, "claims", tuple(self.claims))

    def verified_claims(self) -> tuple[ClaimRecord, ...]:
        """Return the claims admitted to the vetted claim pack.

        Returns:
            The claims with ``VERIFIED`` status, in ledger order.
        """
        return tuple(claim for claim in self.claims if claim.status is ClaimStatus.VERIFIED)

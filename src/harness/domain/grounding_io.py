"""JSON round-trip for the grounding ledger (``pieces/<id>/grounding.json``)."""

import json
from typing import Any

from harness.domain.grounding import (
    ClaimRecord,
    ClaimStatus,
    GroundingLedger,
    RefutationVerdict,
    SourceRecord,
    SourceTier,
)
from harness.errors import MalformedArtifactError


def ledger_to_json(ledger: GroundingLedger) -> str:
    """Serialize a ledger to its ``grounding.json`` text.

    Args:
        ledger: The ledger to serialize.

    Returns:
        Pretty-printed JSON.
    """
    payload = {
        "piece_id": ledger.piece_id,
        "claims": [
            {
                "id": claim.id,
                "text": claim.text,
                "tier": str(claim.tier),
                "status": str(claim.status),
                "refutation": str(claim.refutation) if claim.refutation else None,
                "load_bearing": claim.load_bearing,
                "internal_only": claim.internal_only,
                "sources": [
                    {
                        "citation": source.citation,
                        "tier": str(source.tier),
                        "credibility": source.credibility,
                        "excerpt": source.excerpt,
                        "retrieved_at": source.retrieved_at,
                        "origin_key": source.origin_key,
                    }
                    for source in claim.sources
                ],
            }
            for claim in ledger.claims
        ],
    }
    return json.dumps(payload, indent=2) + "\n"


def ledger_from_json(text: str) -> GroundingLedger:
    """Parse ``grounding.json`` text back into a ledger.

    Args:
        text: The JSON text.

    Returns:
        The parsed ledger.

    Raises:
        MalformedArtifactError: If the JSON does not match the ledger shape.
    """
    try:
        payload: Any = json.loads(text)
        claims = tuple(
            ClaimRecord(
                id=claim["id"],
                text=claim["text"],
                tier=SourceTier(claim["tier"]),
                status=ClaimStatus(claim["status"]),
                refutation=(
                    RefutationVerdict(claim["refutation"]) if claim.get("refutation") else None
                ),
                load_bearing=bool(claim.get("load_bearing", False)),
                internal_only=bool(claim.get("internal_only", False)),
                sources=tuple(
                    SourceRecord(
                        citation=source["citation"],
                        tier=SourceTier(source["tier"]),
                        credibility=source.get("credibility", ""),
                        excerpt=source.get("excerpt", ""),
                        retrieved_at=source.get("retrieved_at", ""),
                        origin_key=source.get("origin_key", ""),
                    )
                    for source in claim.get("sources", ())
                ),
            )
            for claim in payload["claims"]
        )
        return GroundingLedger(piece_id=payload["piece_id"], claims=claims)
    except (KeyError, TypeError, ValueError) as error:
        raise MalformedArtifactError(f"grounding.json is malformed: {error}") from error

"""Decode structured LLM responses into domain artifacts.

Every pipeline purpose has a JSON contract; a response that does not match
raises :class:`~harness.errors.LLMResponseError` — the stage fails loud
rather than papering over a malformed generation.
"""

import json
from typing import Any

from content_graph.domain.blocks import BlockKind, ContentBlock
from content_graph.domain.errors import BlockValidationError, ReservedBlockKindError
from harness.domain.artifacts import PieceArtifact
from harness.domain.plan import ConstellationPlan, PieceConcept, PlannedConnection
from harness.errors import LLMResponseError


def _loads(text: str, purpose: str) -> dict[str, Any]:
    """Parse a JSON object response.

    Args:
        text: The raw response.
        purpose: The purpose, for the error message.

    Returns:
        The parsed object.

    Raises:
        LLMResponseError: If the response is not a JSON object.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise LLMResponseError(f"{purpose}: response is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise LLMResponseError(f"{purpose}: response must be a JSON object")
    return payload


PLAN_RESPONSE_CONTRACT = """\
## Response contract (machine-read — obey exactly)

Respond with a single JSON object with exactly these two top-level keys:

- `"concepts"`: an array of Piece concepts. Each concept object has:
  - `"id"` (string) — a stable slug for the Piece, unique within this plan.
  - `"title"` (string) — the Piece title.
  - `"premise"` (string) — one or two sentences on what the Piece argues.
  - `"topics"` (array of strings) — the Topic ids this Piece is tagged with.
  - `"entry_worthy"` (boolean) — true if this node can open cold as a Daily
    Feature; at least one concept must be `true`.
- `"connections"`: an array of directed Connection edges. Each edge object has:
  - `"from"` (string) — the `id` of the origin concept.
  - `"to"` (string) — the `id` of the destination concept.
  - `"hook_angle"` (string) — the intended hook angle for the Connection.
  - `"rationale"` (string) — why the two Pieces connect.

Use these exact key names. Emit no other top-level keys and no prose outside
the JSON object.\
"""


def decode_plan(text: str) -> ConstellationPlan:
    """Decode an ``architect.plan`` response.

    Args:
        text: The raw response.

    Returns:
        The proposed plan.

    Raises:
        LLMResponseError: On a contract mismatch.
    """
    payload = _loads(text, "architect.plan")
    try:
        concepts = tuple(
            PieceConcept(
                id=str(concept["id"]),
                title=str(concept["title"]),
                premise=str(concept["premise"]),
                topic_ids=tuple(str(topic) for topic in concept["topics"]),
                entry_worthy=bool(concept.get("entry_worthy", False)),
            )
            for concept in payload["concepts"]
        )
        connections = tuple(
            PlannedConnection(
                from_piece_id=str(edge["from"]),
                to_piece_id=str(edge["to"]),
                hook_angle=str(edge["hook_angle"]),
                rationale=str(edge["rationale"]),
            )
            for edge in payload["connections"]
        )
    except (KeyError, TypeError) as error:
        raise LLMResponseError(f"architect.plan: malformed plan payload: {error}") from error
    return ConstellationPlan(concepts=concepts, connections=connections)


def decode_blocks(raw_blocks: object, purpose: str) -> tuple[ContentBlock, ...]:
    """Decode a block list from a writer/editor response.

    Args:
        raw_blocks: The ``blocks`` array from the payload.
        purpose: The purpose, for error messages.

    Returns:
        The validated Content Blocks.

    Raises:
        LLMResponseError: If a block is malformed or uses a reserved kind.
    """
    if not isinstance(raw_blocks, list):
        raise LLMResponseError(f"{purpose}: 'blocks' must be an array")
    blocks: list[ContentBlock] = []
    for raw in raw_blocks:
        if not isinstance(raw, dict) or "kind" not in raw:
            raise LLMResponseError(f"{purpose}: each block needs a 'kind'")
        fields = {key: value for key, value in raw.items() if key != "kind"}
        try:
            blocks.append(ContentBlock(kind=BlockKind(str(raw["kind"])), payload=fields))
        except (ValueError, BlockValidationError, ReservedBlockKindError) as error:
            raise LLMResponseError(f"{purpose}: bad block: {error}") from error
    return tuple(blocks)


def decode_piece_payload(
    text: str, piece_id: str, topic_ids: tuple[str, ...], purpose: str
) -> PieceArtifact:
    """Decode a writer/editor response carrying a full Piece.

    Args:
        text: The raw response.
        piece_id: The Piece id the plan assigned (responses cannot rename).
        topic_ids: The Topic tags the plan assigned.
        purpose: The purpose, for error messages.

    Returns:
        The Piece artifact.

    Raises:
        LLMResponseError: On a contract mismatch.
    """
    payload = _loads(text, purpose)
    read_time = payload.get("read_time_min", 0)
    return PieceArtifact(
        id=piece_id,
        title=str(payload.get("title", "")),
        teaser=str(payload.get("teaser", "")),
        read_time_min=read_time if isinstance(read_time, int) else 0,
        topic_ids=topic_ids,
        blocks=decode_blocks(payload.get("blocks", []), purpose),
    )


def decode_object_list(text: str, key: str, purpose: str) -> tuple[dict[str, Any], ...]:
    """Decode a response whose contract is one array of objects.

    Args:
        text: The raw response.
        key: The array's key in the response object.
        purpose: The purpose, for error messages.

    Returns:
        The array items.

    Raises:
        LLMResponseError: If the key is missing or not an array of objects.
    """
    payload = _loads(text, purpose)
    items = payload.get(key)
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise LLMResponseError(f"{purpose}: {key!r} must be an array of objects")
    return tuple(items)


def decode_object(text: str, purpose: str) -> dict[str, Any]:
    """Decode a response whose contract is a flat JSON object.

    Args:
        text: The raw response.
        purpose: The purpose, for error messages.

    Returns:
        The object.

    Raises:
        LLMResponseError: If the response is not a JSON object.
    """
    return _loads(text, purpose)

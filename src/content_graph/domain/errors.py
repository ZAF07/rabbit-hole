"""Errors raised by the Content Graph domain and through the repository port."""


class ContentGraphError(Exception):
    """Base class for every error the Content Graph raises."""


class BlockValidationError(ContentGraphError, ValueError):
    """A Content Block's payload does not match the contract for its kind."""


class ReservedBlockKindError(BlockValidationError):
    """A visual block kind (image/gif/diagram) was written.

    Visual kinds are reserved slots in V1: valid in the schema so that adding
    visuals later is a data change, but never populated (ADR 0007).
    """


class PieceValidationError(ContentGraphError, ValueError):
    """A Piece violates its own construction contract."""


class TopicValidationError(ContentGraphError, ValueError):
    """A Topic violates its own construction contract."""


class TopicNotFoundError(ContentGraphError, LookupError):
    """A write referenced a Topic id that does not exist in the store."""


class ConnectionValidationError(ContentGraphError, ValueError):
    """A Connection violates its own construction contract."""


class PieceNotFoundError(ContentGraphError, LookupError):
    """A write referenced a Piece id that does not exist in the store."""

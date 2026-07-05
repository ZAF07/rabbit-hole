"""Errors raised by the reader domain and through its ports."""


class ConsumptionError(Exception):
    """Base class for every error the consumption subsystem raises."""


class UnknownUserError(ConsumptionError, LookupError):
    """A navigation action referenced a User id that does not exist."""


class NoJourneyError(ConsumptionError, LookupError):
    """A navigation action was attempted before the reader's journey began."""


class NotCurrentPieceError(ConsumptionError, ValueError):
    """A pull was attempted from a Piece that is not the reader's current position.

    The journey advances one Connection at a time from where the reader
    actually stands; pulling from anywhere else would be a free-roam jump.
    """


class UnknownConnectionError(ConsumptionError, LookupError):
    """A pull named a Connection that does not exist in the Content Graph."""


class FreeRoamError(ConsumptionError, ValueError):
    """An entry named a Piece that is neither the Daily Feature nor already visited.

    V1 is a guided journey, not a search box: a reader may enter only the
    editorially-chosen front door or re-enter ground already in their own
    Personal Knowledge Graph — never an arbitrary Piece across the whole graph.
    """


class CannotBacktrackError(ConsumptionError, ValueError):
    """Backtrack was attempted with nothing above the root of the active thread."""

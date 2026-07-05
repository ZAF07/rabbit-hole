"""Journey — the reader's durable path through the Content Graph.

A single advancing thread with backtracking, not free-roam (ADR 0008). The
``stack`` is the active thread from its root down to where the reader stands;
the ``visited`` nodes and ``pulled`` edges are the deduped history the Personal
Knowledge Graph renders and the honest measure of ground covered. The Journey
outlives any analytics Session and is resumable across app opens.

Every transition returns a new Journey — the domain stays pure; the application
service loads, applies, and saves.
"""

from dataclasses import dataclass, replace

from consumption.domain.errors import CannotBacktrackError, NoJourneyError


@dataclass(frozen=True)
class Edge:
    """A Connection the reader actually pulled: origin -> destination.

    Attributes:
        from_piece_id: The Piece the reader pulled from.
        to_piece_id: The Piece the reader pulled to.
    """

    from_piece_id: str
    to_piece_id: str


@dataclass(frozen=True)
class Journey:
    """A reader's durable path — the substrate the Personal Knowledge Graph builds on.

    Attributes:
        user_id: The owner of the path.
        stack: The active thread, root -> current; ``stack[-1]`` is where the
            reader stands. Backtracking pops it; pulling a Connection pushes.
        visited: Distinct Pieces entered, in first-visit order — the nodes of
            the Personal Knowledge Graph and the depth of ground covered.
            Re-entry never duplicates.
        pulled: Distinct Connections pulled, in order — its edges.
    """

    user_id: str
    stack: tuple[str, ...] = ()
    visited: tuple[str, ...] = ()
    pulled: tuple[Edge, ...] = ()

    @classmethod
    def empty(cls, user_id: str) -> "Journey":
        """Return a fresh, unstarted Journey for a User.

        Args:
            user_id: The owner of the path.

        Returns:
            An empty Journey with no current Piece.
        """
        return cls(user_id=user_id)

    @property
    def current_piece_id(self) -> str | None:
        """The Piece the reader currently stands on, or None if unstarted."""
        return self.stack[-1] if self.stack else None

    @property
    def depth(self) -> int:
        """Session depth — the count of distinct Pieces visited (ground covered)."""
        return len(self.visited)

    def has_visited(self, piece_id: str) -> bool:
        """Whether a Piece is already part of this Journey's covered ground.

        Args:
            piece_id: The Piece to check.

        Returns:
            True if the Piece is already a node in the path.
        """
        return piece_id in self.visited

    def enter(self, piece_id: str) -> "Journey":
        """Root the active thread at a Piece — seed a first Piece or re-enter one.

        Records the Piece as covered ground the first time; a re-entry never
        adds a duplicate node (the trail maps distinct ground, not fidgeting).

        Args:
            piece_id: The Piece to make the head of a fresh active thread.

        Returns:
            The Journey positioned at ``piece_id``.
        """
        return replace(self, stack=(piece_id,), visited=self._with_node(piece_id))

    def pull(self, to_piece_id: str) -> "Journey":
        """Advance the active thread by pulling a Connection to ``to_piece_id``.

        Appends the destination to the path, records the pulled edge, and marks
        new ground covered. Pulling to a Piece already visited records the edge
        without inflating the node set.

        Args:
            to_piece_id: The Connection's destination Piece.

        Returns:
            The Journey advanced to the destination.

        Raises:
            NoJourneyError: If the Journey has not been entered yet.
        """
        origin = self.current_piece_id
        if origin is None:
            raise NoJourneyError("cannot pull a Connection before entering a Piece")
        return replace(
            self,
            stack=(*self.stack, to_piece_id),
            visited=self._with_node(to_piece_id),
            pulled=self._with_edge(Edge(origin, to_piece_id)),
        )

    def backtrack(self) -> "Journey":
        """Step back up the active thread the way the reader came (stack pop).

        Backtracking never removes covered ground — it only moves the reader's
        current position, so a regretted fork does not end the journey.

        Returns:
            The Journey with the top of the active thread popped.

        Raises:
            CannotBacktrackError: If nothing stands above the thread's root.
        """
        if len(self.stack) <= 1:
            raise CannotBacktrackError("nothing to backtrack to above the thread's root")
        return replace(self, stack=self.stack[:-1])

    def _with_node(self, piece_id: str) -> tuple[str, ...]:
        """Append a Piece to visited if new, preserving first-visit order."""
        if piece_id in self.visited:
            return self.visited
        return (*self.visited, piece_id)

    def _with_edge(self, edge: Edge) -> tuple[Edge, ...]:
        """Append an edge to pulled if new, preserving pull order."""
        if edge in self.pulled:
            return self.pulled
        return (*self.pulled, edge)

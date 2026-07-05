"""Unit tests for Connection construction-time validation."""

import pytest

from content_graph.domain.connection import Connection
from content_graph.domain.errors import ConnectionValidationError


def test_connection_requires_non_empty_endpoints_and_hook() -> None:
    with pytest.raises(ConnectionValidationError):
        Connection("", "piece-b", "hook")
    with pytest.raises(ConnectionValidationError):
        Connection("piece-a", "  ", "hook")
    with pytest.raises(ConnectionValidationError):
        Connection("piece-a", "piece-b", "")


def test_connection_cannot_point_at_its_own_origin() -> None:
    with pytest.raises(ConnectionValidationError):
        Connection("piece-a", "piece-a", "a loop")


def test_hook_is_the_connections_own_copy() -> None:
    connection = Connection("piece-a", "piece-b", "The sequel nobody planned for.")
    assert connection.hook == "The sequel nobody planned for."

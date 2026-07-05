"""Issue 06 — the reader loop on the wire, identity, and the boundary held.

Drives the core loop end-to-end over HTTP against the in-memory fakes and
asserts the two boundary guarantees: the wire never carries a generation-only
field (``run_id`` / constellation) and never a branded string.
"""

from dataclasses import fields, is_dataclass
from typing import Any

from fastapi.testclient import TestClient
from tests.consumption.fixture_constellation import CONTAINER, JIT, LOGISTICS, MCLEAN

from api.dependencies import TOKEN_HEADER
from consumption.presentation.vocabulary import VOCABULARY


def _auth(token: str) -> dict[str, str]:
    """A bearer-token Authorization header."""
    return {"Authorization": f"Bearer {token}"}


def _mint(client: TestClient) -> str:
    """First contact: land on the Daily Feature and capture the issued token."""
    response = client.get("/daily")
    assert response.status_code == 200
    token = response.headers.get(TOKEN_HEADER)
    assert token
    return token


def test_first_contact_mints_a_token_and_serves_the_daily_feature(client: TestClient) -> None:
    response = client.get("/daily")

    assert response.status_code == 200
    assert response.headers.get(TOKEN_HEADER)
    body = response.json()
    assert body["piece"]["id"] == CONTAINER
    assert body["piece"]["teaser"] == "How a steel box rewired the world economy."
    assert [c["to_piece_id"] for c in body["connections"]] == [LOGISTICS, MCLEAN]


def test_a_bearer_token_attributes_later_requests_to_the_same_reader(client: TestClient) -> None:
    token = _mint(client)
    client.post(f"/pieces/{CONTAINER}/read", headers=_auth(token))
    client.post(
        "/pull",
        headers=_auth(token),
        json={"from_piece_id": CONTAINER, "to_piece_id": LOGISTICS},
    )

    mine = client.get("/journey", headers=_auth(token))
    assert mine.status_code == 200
    assert mine.json()["current_piece_id"] == LOGISTICS
    assert mine.json()["stack"] == [CONTAINER, LOGISTICS]

    a_stranger = client.get("/journey")  # no token -> a fresh identity, its own path
    assert a_stranger.status_code == 404


def test_a_reused_token_does_not_mint_a_new_identity(client: TestClient) -> None:
    token = _mint(client)

    again = client.get("/daily", headers=_auth(token))

    assert again.status_code == 200
    assert TOKEN_HEADER not in again.headers  # no fresh token: the reader is already known


def test_the_full_loop_runs_end_to_end_over_http(client: TestClient) -> None:
    token = _mint(client)

    read = client.post(f"/pieces/{CONTAINER}/read", headers=_auth(token))
    assert read.status_code == 200
    assert read.json()["piece"]["id"] == CONTAINER
    assert [b["kind"] for b in read.json()["piece"]["blocks"]] == [
        "heading",
        "paragraph",
        "pull-quote",
        "stat-callout",
        "paragraph",
    ]

    pull = client.post(
        "/pull",
        headers=_auth(token),
        json={"from_piece_id": CONTAINER, "to_piece_id": LOGISTICS},
    )
    assert pull.status_code == 200
    assert pull.json()["piece"]["id"] == LOGISTICS

    back = client.post("/backtrack", headers=_auth(token))
    assert back.status_code == 200
    assert back.json()["piece"]["id"] == CONTAINER

    resume = client.get("/resume", headers=_auth(token))
    assert resume.status_code == 200
    assert resume.json()["reading"]["piece"]["id"] == CONTAINER
    assert resume.json()["stack"] == [CONTAINER]

    graph = client.get("/knowledge-graph", headers=_auth(token))
    assert graph.status_code == 200
    nodes = {n["piece_id"] for n in graph.json()["nodes"]}
    edges = {(e["from_piece_id"], e["to_piece_id"]) for e in graph.json()["edges"]}
    assert nodes == {CONTAINER, LOGISTICS}  # distinct ground covered
    assert edges == {(CONTAINER, LOGISTICS)}


def test_no_generation_only_field_reaches_the_wire(client: TestClient) -> None:
    token = _mint(client)
    payloads = _drive_the_loop(client, token)

    blob = "\n".join(payloads)
    assert "run_id" not in blob
    assert "constellation" not in blob
    assert "run-generation-42" not in blob  # the fixture Piece's real run id


def test_no_branded_string_reaches_the_wire(client: TestClient) -> None:
    token = _mint(client)
    payloads = _drive_the_loop(client, token)

    blob = "\n".join(payloads)
    for branded in _branded_strings():
        assert branded not in blob, f"branded string {branded!r} leaked onto the wire"


def test_reading_an_unvisited_non_feature_piece_is_refused_as_free_roam(
    client: TestClient,
) -> None:
    token = _mint(client)

    refused = client.post(f"/pieces/{JIT}/read", headers=_auth(token))

    assert refused.status_code == 403  # V1 is a guided journey, not a search box


def test_pulling_before_reading_is_refused(client: TestClient) -> None:
    token = _mint(client)

    refused = client.post(
        "/pull",
        headers=_auth(token),
        json={"from_piece_id": CONTAINER, "to_piece_id": LOGISTICS},
    )

    assert refused.status_code == 409


def test_pulling_a_nonexistent_connection_is_refused(client: TestClient) -> None:
    token = _mint(client)
    client.post(f"/pieces/{CONTAINER}/read", headers=_auth(token))

    refused = client.post(
        "/pull",
        headers=_auth(token),
        json={"from_piece_id": CONTAINER, "to_piece_id": JIT},  # no direct edge
    )

    assert refused.status_code == 404


def test_backtracking_past_the_root_is_refused(client: TestClient) -> None:
    token = _mint(client)
    client.post(f"/pieces/{CONTAINER}/read", headers=_auth(token))

    refused = client.post("/backtrack", headers=_auth(token))

    assert refused.status_code == 409


def test_resume_without_a_path_returns_no_content(client: TestClient) -> None:
    token = _mint(client)

    resume = client.get("/resume", headers=_auth(token))

    assert resume.status_code == 204


def _drive_the_loop(client: TestClient, token: str) -> list[str]:
    """Run daily -> read -> pull -> backtrack -> resume -> graph, collecting raw bodies."""
    bodies = [client.get("/daily", headers=_auth(token)).text]
    bodies.append(client.get("/notification", headers=_auth(token)).text)
    bodies.append(client.post(f"/pieces/{CONTAINER}/read", headers=_auth(token)).text)
    bodies.append(
        client.post(
            "/pull",
            headers=_auth(token),
            json={"from_piece_id": CONTAINER, "to_piece_id": MCLEAN},
        ).text
    )
    bodies.append(client.post("/backtrack", headers=_auth(token)).text)
    bodies.append(client.get("/journey", headers=_auth(token)).text)
    bodies.append(client.get("/resume", headers=_auth(token)).text)
    bodies.append(client.get("/knowledge-graph", headers=_auth(token)).text)
    return bodies


def _branded_strings() -> set[str]:
    """Every branded string in the presentation vocabulary bundle."""
    collected: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, str):
            collected.add(value)
        elif is_dataclass(value) and not isinstance(value, type):
            for f in fields(value):
                walk(getattr(value, f.name))

    walk(VOCABULARY)
    return collected

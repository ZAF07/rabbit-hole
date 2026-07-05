"""Issue 06 — the anonymous-identity token: mint, verify, and forgery."""

from itertools import count

import pytest

from api.identity import AnonymousIdentity

_SECRET = b"unit-test-secret"


def _identity() -> AnonymousIdentity:
    counter = count(1)
    return AnonymousIdentity(_SECRET, id_factory=lambda: f"user-{next(counter)}")


def test_a_minted_token_verifies_back_to_its_user_id() -> None:
    identity = _identity()

    user_id, token = identity.mint()

    assert identity.verify(token) == user_id


def test_each_mint_issues_a_distinct_identity() -> None:
    identity = _identity()

    first, _ = identity.mint()
    second, _ = identity.mint()

    assert first != second


def test_a_tampered_token_fails_verification() -> None:
    identity = _identity()
    _, token = identity.mint()

    assert identity.verify(token + "x") is None


def test_a_token_signed_with_another_secret_is_rejected() -> None:
    _, token = _identity().mint()
    other = AnonymousIdentity(b"a-different-secret")

    assert other.verify(token) is None


def test_garbage_tokens_fail_closed() -> None:
    identity = _identity()

    for junk in ("", "no-separator", ".", "not-base64.abc", "a.b.c"):
        assert identity.verify(junk) is None


def test_an_empty_secret_is_refused() -> None:
    with pytest.raises(ValueError, match="non-empty signing secret"):
        AnonymousIdentity(b"")

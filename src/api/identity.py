"""Anonymous, device-issued reader identity — the token minted at the edge.

On first contact the API mints an opaque ``user_id`` and a signed token; the
client stores the token and carries it on every later request, and the API
attributes that request to the same reader (ADR 0015). There is no login,
email, or account in V1 — the token *is* the identity.

The token is a stateless HMAC envelope: it carries the ``user_id`` alongside a
signature the server can re-derive, so identity is verifiable without a token
store. The signature is what stops a client forging another reader's id and
reading their trail; a tampered or unsigned token simply fails verification and
first-contact minting takes over.
"""

import base64
import binascii
import hmac
from collections.abc import Callable
from hashlib import sha256
from uuid import uuid4

_SEPARATOR = "."


class AnonymousIdentity:
    """Mints and verifies the reader's opaque, signed identity tokens."""

    def __init__(self, secret: bytes, id_factory: Callable[[], str] | None = None) -> None:
        """Wire the identity minter to its signing secret.

        Args:
            secret: The HMAC signing key; a leak lets a holder forge tokens, so
                it is read from config, never hardcoded.
            id_factory: Mints new opaque user ids; defaults to random UUIDs.
                Injectable so tests get deterministic ids.

        Raises:
            ValueError: If the secret is empty.
        """
        if not secret:
            raise ValueError("AnonymousIdentity requires a non-empty signing secret")
        self._secret = secret
        self._new_user_id = id_factory or (lambda: uuid4().hex)

    def mint(self) -> tuple[str, str]:
        """Issue a fresh reader identity and its signed token.

        Returns:
            A ``(user_id, token)`` pair — the opaque id to attribute the reader
            by and the token the client stores and carries henceforth.
        """
        user_id = self._new_user_id()
        return user_id, self._encode(user_id)

    def verify(self, token: str) -> str | None:
        """Recover the ``user_id`` a token attests to, if its signature holds.

        Args:
            token: The bearer token presented by the client.

        Returns:
            The attested ``user_id``, or None if the token is malformed or its
            signature does not verify (a forged or corrupted token).
        """
        payload, _, signature = token.partition(_SEPARATOR)
        if not payload or not signature:
            return None
        try:
            user_id = base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return None
        if not hmac.compare_digest(signature, self._sign(user_id)):
            return None
        return user_id

    def _encode(self, user_id: str) -> str:
        """Pack a ``user_id`` and its signature into a single opaque token."""
        payload = base64.urlsafe_b64encode(user_id.encode("utf-8")).decode("ascii")
        return f"{payload}{_SEPARATOR}{self._sign(user_id)}"

    def _sign(self, user_id: str) -> str:
        """Derive the hex HMAC-SHA256 signature over a ``user_id``."""
        return hmac.new(self._secret, user_id.encode("utf-8"), sha256).hexdigest()

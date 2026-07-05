"""The presentation vocabulary — the app's ONLY source of branded strings.

An i18n-style bundle keyed by internal term (ADR 0001). UI code renders from
this bundle (``VOCABULARY.piece.one``) instead of hardcoding a branded literal.
The data model, API, and reader domain/application layers **never import it** —
they know only the internal terms. To rebrand or rename the app, edit this one
file; to try an alternate voice, load an alternate bundle. Nothing else changes.

The authoritative internal ↔ UI map lives in ``CONTEXT.md``; this module is its
executable form for the consumption client.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TermPair:
    """Singular and plural branded forms of one internal term."""

    one: str
    many: str


@dataclass(frozen=True)
class SessionTerms:
    """The branded noun and verb for a Session."""

    noun: str
    verb: str


@dataclass(frozen=True)
class Actions:
    """Branded copy for reader actions."""

    follow_connection: str


@dataclass(frozen=True)
class Vocabulary:
    """The full branded bundle, keyed by internal term.

    Attributes:
        app_name: The app's provisional name (deliberately not yet final).
        piece: Branded forms of Piece.
        connection: Branded forms of Connection.
        topic: Branded forms of Topic.
        session: Branded noun/verb for Session.
        personal_knowledge_graph: Branded name for the Personal Knowledge Graph.
        daily_feature: Branded name for the Daily Feature.
        actions: Branded action copy.
    """

    app_name: str
    piece: TermPair
    connection: TermPair
    topic: TermPair
    session: SessionTerms
    personal_knowledge_graph: str
    daily_feature: str
    actions: Actions


VOCABULARY = Vocabulary(
    app_name="Unspool",
    piece=TermPair(one="Thread", many="Threads"),
    connection=TermPair(one="Loose Thread", many="Loose Threads"),
    topic=TermPair(one="Spool", many="Spools"),
    session=SessionTerms(noun="Unspool", verb="unspooling"),
    personal_knowledge_graph="Tapestry",
    daily_feature="Today's Thread",
    actions=Actions(follow_connection="Pull this thread"),
)

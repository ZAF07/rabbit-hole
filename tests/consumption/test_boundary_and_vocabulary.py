"""Issue 01 — the two boundary guards: no branded strings, no generation fields.

These are structural tests: they read the reader's own source tree and assert
the seams of ADR 0001 (branded strings live only in the presentation bundle)
and ADR 0006 (no generation-only field is reachable through a read model).
"""

import dataclasses
import io
import tokenize
from pathlib import Path

from tests.consumption.fixture_constellation import CONTAINER

from consumption.application.reader import ReaderService
from consumption.presentation.vocabulary import VOCABULARY

REPO_ROOT = Path(__file__).resolve().parents[2]
CONSUMPTION_SRC = REPO_ROOT / "src" / "consumption"
DOMAIN_AND_APPLICATION = (
    CONSUMPTION_SRC / "domain",
    CONSUMPTION_SRC / "application",
)

GAMIFICATION_PRIMITIVES = ("streak", "badge", "point", "leaderboard")

BRANDED_STRINGS = (
    "Thread",
    "Threads",
    "Loose Thread",
    "Spool",
    "Unspool",
    "Tapestry",
    "Today's Thread",
    "Pull this thread",
)

GENERATION_ONLY_TERMS = ("run_id", "constellation")


def _reader_source_files() -> list[Path]:
    return [path for root in DOMAIN_AND_APPLICATION for path in root.rglob("*.py")]


def _code_identifiers(source: str) -> set[str]:
    """The NAME tokens of a module — its real code, docstrings/comments excluded."""
    names: set[str] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.NAME:
            names.add(token.string)
    return names


def test_branded_strings_render_only_from_the_presentation_bundle() -> None:
    assert VOCABULARY.piece.one == "Thread"
    assert VOCABULARY.personal_knowledge_graph == "Tapestry"
    assert VOCABULARY.daily_feature == "Today's Thread"
    assert VOCABULARY.actions.follow_connection == "Pull this thread"


def test_domain_and_application_use_internal_vocabulary_only() -> None:
    for path in _reader_source_files():
        source = path.read_text(encoding="utf-8")
        assert "consumption.presentation" not in source, f"{path} imports the presentation layer"
        for branded in BRANDED_STRINGS:
            assert branded not in source, f"{path} uses the branded string {branded!r}"


def test_reader_code_never_references_a_generation_only_field() -> None:
    for path in _reader_source_files():
        identifiers = _code_identifiers(path.read_text(encoding="utf-8"))
        leaked = identifiers & set(GENERATION_ONLY_TERMS)
        assert not leaked, f"{path} references generation-only field(s) {leaked} in code"


def test_no_gamification_primitive_exists_anywhere_in_the_reader() -> None:
    for path in CONSUMPTION_SRC.rglob("*.py"):
        identifiers = _code_identifiers(path.read_text(encoding="utf-8"))
        for name in identifiers:
            parts = name.lower().split("_")
            named = [
                primitive
                for primitive in GAMIFICATION_PRIMITIVES
                if any(part.startswith(primitive) for part in parts)
            ]
            assert not named, f"{path} implements gamification primitive(s) {named} via {name!r}"


def test_read_models_expose_no_generation_only_field(reader: ReaderService) -> None:
    reading = reader.read_piece(CONTAINER)

    assert reading is not None
    piece_fields = {field.name for field in dataclasses.fields(reading.piece)}
    assert not (piece_fields & set(GENERATION_ONLY_TERMS))
    assert not hasattr(reading.piece, "run_id")
    for preview in reading.connections:
        preview_fields = {field.name for field in dataclasses.fields(preview)}
        assert not (preview_fields & set(GENERATION_ONLY_TERMS))

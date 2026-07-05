"""Banned-filler phrases, parsed from the guardrail spec itself.

The list lives in ``harness/guardrails/piece.md`` (the D3 section) — data,
not code — so a Distiller-proposed, human-ratified addition takes effect with
no code change. ``___`` and ``…`` inside a phrase are wildcards.
"""

import re

_BANNED_HEADING = "## Banned-filler phrases"
_QUOTED = re.compile(r'"([^"]+)"')
_WILDCARD_GAP = r".{0,40}?"


def parse_banned_phrases(markdown: str) -> tuple[str, ...]:
    """Extract the banned-phrase list from the piece-guardrail spec text.

    Args:
        markdown: The full text of ``harness/guardrails/piece.md``.

    Returns:
        Every quoted phrase in the banned-list section, in document order.
    """
    phrases: list[str] = []
    in_section = False
    for line in markdown.splitlines():
        if line.startswith("## "):
            in_section = line.startswith(_BANNED_HEADING)
            continue
        if in_section and line.lstrip().startswith("- "):
            phrases.extend(_QUOTED.findall(line))
    return tuple(phrases)


def compile_phrase(phrase: str) -> re.Pattern[str]:
    """Compile one banned phrase into a case-insensitive matcher.

    Args:
        phrase: The phrase as written in the spec; ``___`` and ``…`` match
            any short run of words.

    Returns:
        A compiled pattern anchored on a word boundary.
    """
    escaped = re.escape(phrase).replace("___", _WILDCARD_GAP).replace("…", _WILDCARD_GAP)
    return re.compile(rf"\b{escaped}", re.IGNORECASE)


def find_banned(text: str, banned_phrases: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Return the banned phrases that occur in a text.

    Args:
        text: The prose to scan.
        banned_phrases: The phrase list (typically from
            :func:`parse_banned_phrases`).

    Returns:
        The phrases that matched, in list order, each at most once.
    """
    return tuple(phrase for phrase in banned_phrases if compile_phrase(phrase).search(text))

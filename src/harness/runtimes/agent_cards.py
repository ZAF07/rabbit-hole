"""Split the agent roster into Claude Code subagent files — one spec, two runtimes.

``harness/agents/README.md`` is the design-time home of the seven spec
cards. At build time each card becomes ``.claude/agents/<name>.md`` with the
frontmatter Claude Code expects; the card body is carried verbatim, so the
subagent obeys exactly the markdown the LangGraph nodes read (ADR 0010).
Regeneration is deterministic — rerunning over an unchanged roster rewrites
identical files.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from harness.errors import MalformedArtifactError

_CARD_HEADING = re.compile(r"^## \d+ · (?P<name>[A-Za-z]+) — (?P<tagline>.+?)$")
_TOOLS_LINE = re.compile(r"^- \*\*Tools:\*\* (?P<tools>.+)$")
_PORT_NAME = re.compile(r"`([A-Za-z]+Port|ContentGraphRepository)`")


@dataclass(frozen=True)
class AgentCard:
    """One agent's spec card, split out of the roster.

    Attributes:
        name: The agent's lowercase name (the subagent file stem).
        description: The card's tagline, markdown emphasis stripped.
        tools: The ports the card grants, in card order; empty for the
            pure file-in / file-out agents.
        body: The card's full markdown body, verbatim.
    """

    name: str
    description: str
    tools: tuple[str, ...]
    body: str


def parse_agent_cards(roster_text: str) -> tuple[AgentCard, ...]:
    """Split the roster markdown into its numbered agent cards.

    Args:
        roster_text: The full text of ``harness/agents/README.md``.

    Returns:
        The seven cards, in roster order.

    Raises:
        MalformedArtifactError: If no numbered agent card is found.
    """
    cards: list[AgentCard] = []
    name: str | None = None
    tagline = ""
    body: list[str] = []

    def flush() -> None:
        """Finish the card being accumulated, if one is open."""
        if name is None:
            return
        text = "\n".join(body).strip() + "\n"
        tools: tuple[str, ...] = ()
        for line in body:
            match = _TOOLS_LINE.match(line.strip())
            if match:
                tools = tuple(_PORT_NAME.findall(match.group("tools")))
                break
        cards.append(
            AgentCard(
                name=name.casefold(),
                description=re.sub(r"[*_]", "", tagline).strip(),
                tools=tools,
                body=text,
            )
        )

    for line in roster_text.splitlines():
        if line.startswith("## "):
            flush()
            name, tagline, body = None, "", []
            match = _CARD_HEADING.match(line)
            if match:
                name = match.group("name")
                tagline = match.group("tagline")
            continue
        if name is not None:
            body.append(line)
    flush()
    if not cards:
        raise MalformedArtifactError("no numbered agent cards found in the roster")
    return tuple(cards)


def render_subagent(card: AgentCard) -> str:
    """Render one card as a Claude Code subagent file.

    Args:
        card: The parsed card.

    Returns:
        The subagent markdown: frontmatter (name, description, and the
        granted ports as tools, when any) followed by the card body.
    """
    lines = ["---", f"name: {card.name}", f"description: {card.description}"]
    if card.tools:
        lines.append(f"tools: {', '.join(card.tools)}")
    lines.extend(["---", "", card.body])
    return "\n".join(lines)


def write_agent_cards(roster_text: str, out_dir: Path) -> tuple[Path, ...]:
    """Generate every ``.claude/agents/<name>.md`` subagent file.

    Args:
        roster_text: The full text of ``harness/agents/README.md``.
        out_dir: The target directory (``.claude/agents``).

    Returns:
        The written paths, in roster order.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for card in parse_agent_cards(roster_text):
        target = out_dir / f"{card.name}.md"
        target.write_text(render_subagent(card))
        written.append(target)
    return tuple(written)

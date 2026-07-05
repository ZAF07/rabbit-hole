"""A tiny front-matter dialect shared by every run-workspace deliverable.

Deliberately smaller than YAML — scalars, ``key: >`` folded text, and
``- item`` lists — so deliverables stay human-editable without pulling a
YAML dependency into the domain.
"""

import re

_COMMENT = re.compile(r"\s+#.*$")
_DELIMITER = "---"


def split_frontmatter(text: str) -> tuple[dict[str, str | list[str]], str]:
    """Split a deliverable into its front-matter fields and its body.

    Args:
        text: The full file text, optionally starting with a ``---`` block.

    Returns:
        A (fields, body) pair. Fields map keys to scalar strings or lists;
        the body is everything after the closing delimiter, stripped.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _DELIMITER:
        return {}, text.strip()
    fields: dict[str, str | list[str]] = {}
    key: str | None = None
    folding = False
    body_start = len(lines)
    for index, raw in enumerate(lines[1:], start=1):
        if raw.strip() == _DELIMITER:
            body_start = index + 1
            break
        line = _COMMENT.sub("", raw.rstrip())
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if folding and key is not None and raw.startswith((" ", "\t")):
            existing = fields.get(key, "")
            joined = f"{existing} {stripped}".strip() if isinstance(existing, str) else stripped
            fields[key] = joined
            continue
        folding = False
        if stripped.startswith("- ") and key is not None:
            values = fields.setdefault(key, [])
            if isinstance(values, list):
                values.append(stripped[2:].strip())
            continue
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", stripped)
        if match:
            key, value = match.group(1), match.group(2).strip()
            if value == ">":
                fields[key] = ""
                folding = True
            elif value == "":
                fields[key] = []
            else:
                fields[key] = value
    body = "\n".join(lines[body_start:]).strip()
    return fields, body


def render_frontmatter(fields: dict[str, str | int | bool | list[str]], body: str = "") -> str:
    """Render fields (and an optional body) back into deliverable text.

    Args:
        fields: The front-matter fields; lists render as ``- item`` blocks.
        body: The markdown body to append after the closing delimiter.

    Returns:
        The full file text, ending in a single trailing newline.
    """
    lines = [_DELIMITER]
    for key, value in fields.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {item}" for item in value)
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {value}")
    lines.append(_DELIMITER)
    if body:
        lines.extend(["", body])
    return "\n".join(lines).rstrip() + "\n"

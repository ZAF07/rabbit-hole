"""Loader for the shared stage manifest (``harness/manifest.toml``).

The manifest is data, not code — the single source of truth for
``stage → agent → deliverable → prerequisite → gate`` that both the
LangGraph runtime and the Claude Code subagent wiring consume (ADR 0010).
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StageSpec:
    """One pipeline stage as declared in the manifest.

    Attributes:
        number: The fixed position in stage order.
        name: The stage's short name (``plan``, ``source``, …).
        agent: The owning agent's name; empty for agentless steps.
        fan_out: ``"once"`` or ``"per_piece"``.
        deliverables: Workspace-relative paths this stage must produce;
            ``{piece_id}`` expands per planned Piece.
        prerequisites: Paths that must exist before the stage may start.
        gate: The human-readable statement of the stage's done-contract.
    """

    number: int
    name: str
    agent: str
    fan_out: str
    deliverables: tuple[str, ...]
    prerequisites: tuple[str, ...]
    gate: str

    def expand(self, template: str, piece_id: str | None = None) -> str:
        """Expand a path template for one Piece.

        Args:
            template: A manifest path, possibly containing ``{piece_id}``.
            piece_id: The Piece to expand for.

        Returns:
            The concrete workspace-relative path.

        Raises:
            ValueError: If the template needs a piece id and none was given.
        """
        if "{piece_id}" in template:
            if piece_id is None:
                raise ValueError(f"path template {template!r} requires a piece_id")
            return template.replace("{piece_id}", piece_id)
        return template


@dataclass(frozen=True)
class HumanGateSpec:
    """One of the three human gates (ADR 0013), as declared in the manifest.

    Attributes:
        name: The gate name (``plan`` / ``piece`` / ``constellation``).
        after_stage: The stage whose completion triggers this gate.
        target: The workspace-relative artifact the human reviews.
        per_piece: True if the gate runs once per Piece.
    """

    name: str
    after_stage: str
    target: str
    per_piece: bool

    def expand_target(self, piece_id: str | None = None) -> str:
        """Expand the reviewed artifact's path for one Piece.

        Args:
            piece_id: The Piece under review, for per-piece gates.

        Returns:
            The concrete workspace-relative path.

        Raises:
            ValueError: If the gate is per-piece and no id was given.
        """
        if "{piece_id}" in self.target:
            if piece_id is None:
                raise ValueError(f"gate {self.name!r} target requires a piece_id")
            return self.target.replace("{piece_id}", piece_id)
        return self.target


@dataclass(frozen=True)
class StageManifest:
    """The whole parsed manifest.

    Attributes:
        stages: Every stage, in fixed pipeline order.
        human_gates: The three human gates.
    """

    stages: tuple[StageSpec, ...]
    human_gates: tuple[HumanGateSpec, ...]

    def stage(self, name: str) -> StageSpec:
        """Look up a stage by name.

        Args:
            name: The stage's short name.

        Returns:
            The stage spec.

        Raises:
            KeyError: If no stage has that name.
        """
        for spec in self.stages:
            if spec.name == name:
                return spec
        raise KeyError(f"no stage named {name!r} in the manifest")

    def human_gate(self, name: str) -> HumanGateSpec:
        """Look up a human gate by name.

        Args:
            name: The gate name.

        Returns:
            The gate spec.

        Raises:
            KeyError: If no gate has that name.
        """
        for spec in self.human_gates:
            if spec.name == name:
                return spec
        raise KeyError(f"no human gate named {name!r} in the manifest")


def load_manifest(path: Path) -> StageManifest:
    """Load and order the stage manifest from disk.

    Args:
        path: The path to ``harness/manifest.toml``.

    Returns:
        The parsed manifest, stages sorted by their fixed number.
    """
    payload = tomllib.loads(path.read_text())
    stages = tuple(
        sorted(
            (
                StageSpec(
                    number=int(stage["number"]),
                    name=str(stage["name"]),
                    agent=str(stage.get("agent", "")),
                    fan_out=str(stage.get("fan_out", "once")),
                    deliverables=tuple(stage.get("deliverables", ())),
                    prerequisites=tuple(stage.get("prerequisites", ())),
                    gate=str(stage.get("gate", "")),
                )
                for stage in payload.get("stages", ())
            ),
            key=lambda spec: spec.number,
        )
    )
    gates = tuple(
        HumanGateSpec(
            name=str(gate["name"]),
            after_stage=str(gate["after_stage"]),
            target=str(gate["target"]),
            per_piece=bool(gate.get("per_piece", False)),
        )
        for gate in payload.get("human_gates", ())
    )
    return StageManifest(stages=stages, human_gates=gates)

"""Access to the markdown source of truth under ``harness/`` (ADR 0010).

The DNA, Voice Profiles, guardrail specs, agent cards, and the stage
manifest are files a human edits; both runtimes read them through this
library so behavior changes with no code change.
"""

from dataclasses import dataclass
from pathlib import Path

from harness.guardrails.phrases import parse_banned_phrases
from harness.manifest import StageManifest, load_manifest


@dataclass(frozen=True)
class SpecLibrary:
    """Resolves and reads the harness's markdown artifacts.

    Attributes:
        repo_root: The repository root containing ``harness/`` and ``docs/``.
    """

    repo_root: Path

    @property
    def harness_dir(self) -> Path:
        """The harness artifact root.

        Returns:
            ``<repo>/harness``.
        """
        return self.repo_root / "harness"

    def dna_text(self) -> str:
        """Read the Editorial DNA.

        Returns:
            The text of ``harness/editorial/dna.md``.
        """
        return (self.harness_dir / "editorial" / "dna.md").read_text()

    def voice_text(self, name: str) -> str:
        """Read a Voice Profile by name.

        Args:
            name: The profile's file stem, e.g. ``"narrative-nonfiction"``.

        Returns:
            The profile text.
        """
        return (self.harness_dir / "editorial" / "voices" / f"{name}.md").read_text()

    def guardrail_text(self, name: str) -> str:
        """Read a guardrail spec by name.

        Args:
            name: ``piece`` / ``connection`` / ``constellation`` / ``sourcing``.

        Returns:
            The spec text.
        """
        return (self.harness_dir / "guardrails" / f"{name}.md").read_text()

    def agent_roster_text(self) -> str:
        """Read the agent spec cards.

        Returns:
            The text of ``harness/agents/README.md``.
        """
        return (self.harness_dir / "agents" / "README.md").read_text()

    def taxonomy_text(self) -> str:
        """Read the seed Topic taxonomy design doc.

        Returns:
            The text of ``docs/taxonomy.md``.
        """
        return (self.repo_root / "docs" / "taxonomy.md").read_text()

    def banned_phrases(self) -> tuple[str, ...]:
        """Parse the live banned-filler list out of the piece guardrail.

        Returns:
            The phrases.
        """
        return parse_banned_phrases(self.guardrail_text("piece"))

    def manifest(self) -> StageManifest:
        """Load the shared stage manifest.

        Returns:
            The parsed manifest.
        """
        return load_manifest(self.harness_dir / "manifest.toml")

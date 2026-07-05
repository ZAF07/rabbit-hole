"""The run workspace — ``harness/runs/<id>/`` — where deliverables ARE the gates.

Every stage reads and writes files here; a stage's start precondition is the
existence of its prerequisite artifacts (the we-os discipline, ADR 0010).
There is no implicit in-memory state a resumed run could disagree with.
"""

from pathlib import Path

from harness.errors import MissingPrerequisiteError


class RunWorkspace:
    """Path discipline and gate checks for one run's file workspace."""

    def __init__(self, root: Path) -> None:
        """Bind the workspace to its root directory.

        Args:
            root: The run directory (``harness/runs/<id>``), created lazily.
        """
        self.root = root

    def path(self, relative: str) -> Path:
        """Resolve a workspace-relative path.

        Args:
            relative: The path as written in the manifest.

        Returns:
            The absolute path.
        """
        return self.root / relative

    def exists(self, relative: str) -> bool:
        """Check whether a deliverable exists.

        Args:
            relative: The workspace-relative path.

        Returns:
            True if the file is present.
        """
        return self.path(relative).is_file()

    def read(self, relative: str) -> str:
        """Read a deliverable's text.

        Args:
            relative: The workspace-relative path.

        Returns:
            The file text.

        Raises:
            MissingPrerequisiteError: If the deliverable is absent.
        """
        target = self.path(relative)
        if not target.is_file():
            raise MissingPrerequisiteError(f"deliverable missing: {relative}")
        return target.read_text()

    def write(self, relative: str, text: str) -> Path:
        """Write a deliverable, creating parent directories.

        Args:
            relative: The workspace-relative path.
            text: The file text.

        Returns:
            The written path.
        """
        target = self.path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        return target

    def append(self, relative: str, text: str) -> Path:
        """Append to an append-only deliverable (e.g. ``feedback/verdicts.jsonl``).

        Args:
            relative: The workspace-relative path.
            text: The text to append.

        Returns:
            The appended-to path.
        """
        target = self.path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a") as handle:
            handle.write(text)
        return target

    def require(self, stage_name: str, *relatives: str) -> None:
        """Enforce the gate: refuse to start a stage without its prerequisites.

        Args:
            stage_name: The stage asking to start (for the error message).
            *relatives: The workspace-relative prerequisite paths.

        Raises:
            MissingPrerequisiteError: If any prerequisite is absent.
        """
        missing = [relative for relative in relatives if not self.exists(relative)]
        if missing:
            raise MissingPrerequisiteError(
                f"stage {stage_name!r} refused to start; missing prerequisite deliverable(s): "
                f"{', '.join(missing)}"
            )

    def preserve_machine_copy(self, relative: str) -> Path:
        """Preserve the machine's output beside the human's working copy.

        The copy lands at ``<stem>.machine<suffix>`` and is written only
        once — diff-by-preservation (ADR 0013) needs the original untouched.

        Args:
            relative: The workspace-relative deliverable path.

        Returns:
            The machine-copy path.
        """
        source = self.path(relative)
        machine = source.with_name(f"{source.stem}.machine{source.suffix}")
        if not machine.exists():
            machine.write_text(source.read_text())
        return machine

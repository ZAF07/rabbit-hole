"""Errors the harness raises — every one of them is a loud, early failure."""


class HarnessError(Exception):
    """Base class for every error the generation harness raises."""


class BriefValidationError(HarnessError, ValueError):
    """A Theme Brief is malformed or carries an unfilled placeholder."""


class MissingPrerequisiteError(HarnessError, FileNotFoundError):
    """A stage was asked to start without its prerequisite deliverable on disk."""


class MalformedArtifactError(HarnessError, ValueError):
    """A run-workspace deliverable could not be parsed back into its artifact."""


class LLMResponseError(HarnessError, ValueError):
    """An LLM response did not match the structured contract for its purpose."""


class ThinSourcePackError(HarnessError):
    """A Piece's vetted claim pack is too thin to draft from (fails before the Writer)."""


class QABudgetExceededError(HarnessError):
    """The Editor's machine-QA loop spent its budget without reaching a pass."""


class GroundingDriftError(HarnessError):
    """A drafted assertion could not be mapped back to a verified claim (Stage 4.5)."""


class ContractViolationError(HarnessError):
    """The run's output violates the Tier-1 outcome contract (I1–I8)."""


class PublishIntegrityError(HarnessError):
    """The publish step could not produce a contract-valid survivor set."""

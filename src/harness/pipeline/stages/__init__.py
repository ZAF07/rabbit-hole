"""The seven pipeline stages, each a bounded loop behind a file gate.

Every stage: refuses to start without its manifest prerequisites on disk,
skips work whose deliverable already exists (resume idempotence), does its
job through the ports, and writes its deliverable — which is the next
stage's gate.

The stages are split one deep module per agent (the roster of ADR 0010's
Stage|Owner table), with the cross-agent helpers — workspace paths, the
per-Piece fan-out, the Brief/plan loaders, and the constellation assembler —
in :mod:`harness.pipeline.stages._kernel`. This package's namespace re-exports
the whole surface, so ``stages.run_stage_*`` and the shared helpers are
imported exactly as before; the split is invisible to both runtimes and to the
publish gate.
"""

from harness.pipeline.stages._kernel import (
    CONNECTIONS,
    GOAL,
    PLAN,
    QA,
    _fan_out,
    _record_failure,
    assemble_constellation,
    constellation_from_workspace,
    draft_path,
    expanded_prerequisites,
    failure_path,
    grounding_path,
    has_failed,
    load_brief,
    load_plan,
    piece_path,
    sources_path,
    voice_name,
)
from harness.pipeline.stages.architect import run_stage_gate0, run_stage_plan
from harness.pipeline.stages.editor import run_stage_edit
from harness.pipeline.stages.researcher import admit_claim, run_stage_source
from harness.pipeline.stages.reviewer import run_stage_qa
from harness.pipeline.stages.weaver import run_stage_wire
from harness.pipeline.stages.writer import run_stage_draft

__all__ = [
    "CONNECTIONS",
    "GOAL",
    "PLAN",
    "QA",
    "_fan_out",
    "_record_failure",
    "admit_claim",
    "assemble_constellation",
    "constellation_from_workspace",
    "draft_path",
    "expanded_prerequisites",
    "failure_path",
    "grounding_path",
    "has_failed",
    "load_brief",
    "load_plan",
    "piece_path",
    "run_stage_draft",
    "run_stage_edit",
    "run_stage_gate0",
    "run_stage_plan",
    "run_stage_qa",
    "run_stage_source",
    "run_stage_wire",
    "sources_path",
    "voice_name",
]

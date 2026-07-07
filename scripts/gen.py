"""In-process driver for a human-gated generation run (dev/operator tool).

The HTTP admin trigger (``POST /admin/generation/runs``) mints a fresh run id
per call and reports a paused run as ``succeeded`` — fine for an unattended or
first-leg kick-off, but it cannot *resume* a run through its human gates. This
script closes that gap: it builds the same ``RunContext`` the API composition
root builds (Postgres Content Graph, the real DeepSeek adapter, Playwright web,
and the real ``WorkspaceVerdictGates``), but pins the run id so re-invoking
resumes off the workspace deliverables (ADR 0013, ADR 0016).

Usage:
    # 1. start (or resume) a run — writes goal.md on first call, then runs to
    #    the first gate awaiting a verdict:
    uv run python scripts/gen.py run my-run --brief "How the printing press ..."

    # 2. review the paused artifact in harness/runs/my-run/, then approve it:
    uv run python scripts/gen.py verdict my-run --gate plan --approve

    # 3. resume — carries on to the next gate:
    uv run python scripts/gen.py run my-run

Nothing here is imported by the reader path; it is an operator convenience that
uses only the harness's public ports (ADR 0006).
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from content_graph.adapters.postgres import PostgresContentGraphRepository
from content_graph.config import ContentGraphConfig
from harness.adapters.llm_factory import build_llm
from harness.adapters.playwright_web import PlaywrightWebSource
from harness.config import LLMConfig
from harness.pipeline.context import HarnessConfig, RunContext
from harness.pipeline.graph import run_pipeline
from harness.review.gates import GatePolicy
from harness.review.surface import WorkspaceVerdictGates, record_verdict
from harness.specs import SpecLibrary
from harness.workspace import RunWorkspace

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = REPO_ROOT / "harness" / "runs"


def _harness_config(llm_config: LLMConfig) -> HarnessConfig:
    """Build the run knobs, stamping the real model identity on every verdict.

    Args:
        llm_config: The resolved LLM configuration.

    Returns:
        The harness config with ``runtime`` and ``model`` set for the
        verdict log.
    """
    model = f"{llm_config.provider}:{llm_config.precise.model}/{llm_config.creative.model}"
    return HarnessConfig(runtime="langgraph", model=model, fan_out=4)


def _build_context(run_id: str, *, gates: GatePolicy) -> tuple[RunContext, PlaywrightWebSource]:
    """Assemble a run context wired to real Postgres, DeepSeek, and Playwright.

    Args:
        run_id: The run identity (also its workspace directory name).
        gates: The human-gate policy in force.

    Returns:
        The run context and the web adapter (returned so the caller can
        close its browser pool when the process is done).
    """
    llm_config = LLMConfig.from_env()
    repo = PostgresContentGraphRepository.from_config(ContentGraphConfig.from_env())
    web = PlaywrightWebSource()
    specs = SpecLibrary(repo_root=REPO_ROOT)
    workspace = RunWorkspace(RUNS_ROOT / run_id)
    context = RunContext(
        run_id=run_id,
        workspace=workspace,
        specs=specs,
        manifest=specs.manifest(),
        llm=build_llm(llm_config),
        web=web,
        repo=repo,
        gates=gates,
        config=_harness_config(llm_config),
    )
    return context, web


def _cmd_run(args: argparse.Namespace) -> int:
    """Start or resume a run, printing where it paused and what to do next.

    Args:
        args: Parsed CLI arguments (``run_id``, optional ``brief``).

    Returns:
        A process exit code.
    """
    workspace = RunWorkspace(RUNS_ROOT / args.run_id)
    if not workspace.exists("goal.md"):
        if not args.brief:
            print(
                f"run {args.run_id!r} is new — pass --brief to seed goal.md",
                file=sys.stderr,
            )
            return 2
        workspace.write("goal.md", args.brief)

    context, web = _build_context(args.run_id, gates=WorkspaceVerdictGates())
    try:
        state = run_pipeline(context)
    finally:
        web.close()

    status = state.get("status", "running")
    detail = state.get("detail", "")
    print(f"\nrun {args.run_id}: {status}" + (f" — {detail}" if detail else ""))
    if status == "paused":
        print(f"  review the artifact under harness/runs/{args.run_id}/,")
        print("  then record a verdict and re-run this command to resume.")
    return 0


def _cmd_verdict(args: argparse.Namespace) -> int:
    """Record an approve/reject verdict for one gate target.

    ``edit_approve`` is not a choice here — edit the working copy first and
    pass ``--approve``; the machine->human diff is detected and the verdict
    is upgraded automatically (ADR 0013).

    Args:
        args: Parsed CLI arguments (``run_id``, ``gate``, ``target``,
            ``approve``/``reason``).

    Returns:
        A process exit code.
    """
    specs = SpecLibrary(repo_root=REPO_ROOT)
    gate = specs.manifest().human_gate(args.gate)
    workspace = RunWorkspace(RUNS_ROOT / args.run_id)
    if gate.per_piece and not args.target:
        print("the piece gate needs --target <piece_id>", file=sys.stderr)
        return 2
    target_id = args.target if gate.per_piece else gate.name
    verdict = "approve" if args.approve else "reject"
    llm_config = LLMConfig.from_env()
    record = record_verdict(
        workspace,
        gate,
        target_id,
        verdict,
        run_id=args.run_id,
        runtime="langgraph",
        model=f"{llm_config.provider}:{llm_config.precise.model}/{llm_config.creative.model}",
        reason=args.reason or "",
    )
    print(f"recorded {record.verdict} for {gate.name}/{target_id}")
    return 0


def _parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``run`` and ``verdict`` subcommands.

    Returns:
        The configured parser.
    """
    parser = argparse.ArgumentParser(description="Drive a human-gated generation run in-process.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="start or resume a run up to its next human gate")
    run.add_argument("run_id", help="the run's stable id (its workspace directory name)")
    run.add_argument("--brief", help="the through-line; required only on the first call", default="")
    run.set_defaults(func=_cmd_run)

    verdict = sub.add_parser("verdict", help="record an approve/reject at a gate")
    verdict.add_argument("run_id", help="the run's id")
    verdict.add_argument("--gate", required=True, choices=("plan", "piece", "constellation"))
    verdict.add_argument("--target", help="the Piece id (piece gate only)", default="")
    decision = verdict.add_mutually_exclusive_group(required=True)
    decision.add_argument("--approve", action="store_true", help="approve the artifact")
    decision.add_argument("--reject", dest="approve", action="store_false", help="reject it")
    verdict.add_argument("--reason", help="required for a reject (the Distiller learns from it)")
    verdict.set_defaults(func=_cmd_verdict)
    return parser


def main() -> int:
    """Load the environment and dispatch the chosen subcommand.

    Returns:
        A process exit code.
    """
    load_dotenv(REPO_ROOT / ".env")
    args = _parser().parse_args()
    exit_code: int = args.func(args)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

"""The shared ``harness`` CLI — the deterministic seam both runtimes call (ADR 0019).

Claude Code and the in-process human driver both invoke this console script via
``Bash``; it exposes exactly the machinery that must be *identical* across
runtimes — the binary Tier-1 guardrails, the recall-first fetch, the verdict
log, and the atomic publish write — as thin adapters over already-shipped pure
functions. It is generation-only (ADR 0006) and imports nothing from
consumption.

The module is split into a testable core — :func:`run_cli`, which executes one
subcommand over **injected** dependencies and returns an exit code while writing
structured JSON to stdout — and a thin :func:`main`, which resolves the real
adapters from environment config (mirroring ``build_app_from_env`` in
``api/main.py``) and delegates to the core. Only the core is unit-tested.
"""

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from content_graph.ports.repository import ContentGraphRepository
from harness.domain.piece_io import parse_piece
from harness.errors import HarnessError
from harness.guardrails.constellation import evaluate_constellation
from harness.guardrails.piece import evaluate_piece
from harness.guardrails.violations import Violation
from harness.pipeline import publish, stages
from harness.pipeline.context import HarnessConfig, RunContext
from harness.pipeline.graph import run_pipeline
from harness.pipeline.stages import constellation_from_workspace, piece_path
from harness.ports.llm import LLMPort
from harness.ports.web_source import FetchedPage, WebSourcePort
from harness.review.gates import GatePolicy, GateStatus, preserve_and_decide
from harness.review.surface import WorkspaceVerdictGates, read_verdicts, record_verdict
from harness.specs import SpecLibrary
from harness.workspace import RunWorkspace


class CliError(HarnessError):
    """A CLI invocation could not be carried out (a bad target, an absent port)."""


class _UnwiredWeb(WebSourcePort):
    """A web port stand-in for commands that never fetch (publish's re-wire).

    Present so ``context`` can always build a valid :class:`RunContext`; any
    call is a wiring bug, not a runtime path.
    """

    def fetch(self, url: str) -> FetchedPage | None:
        """Refuse — a command that reached here should have wired a real port.

        Args:
            url: The URL a caller tried to fetch.

        Raises:
            CliError: Always.
        """
        raise CliError("this command has no web source port wired")


_UNWIRED_WEB = _UnwiredWeb()


@dataclass(frozen=True)
class CliDeps:
    """The injected dependencies one CLI invocation runs over.

    The read commands (``check-piece`` / ``check-constellation`` / ``verdict``)
    need only the workspace root and the specs; the port-backed commands
    (``fetch`` / ``publish`` / ``run``) fill the ports they require. Tests inject
    the offline fixture substrate; :func:`main` injects the real adapters.

    Attributes:
        runs_root: The directory holding every run workspace
            (``harness/runs``); a run's workspace is ``runs_root/<run_id>``.
        specs: The markdown source of truth (banned phrases, manifest).
        config: The run knobs (records ``runtime``/``model`` on verdicts).
        web: The web-sourcing port, wired for ``fetch`` and ``run``.
        llm: The model port, wired for ``publish`` and ``run``.
        repo: The Content Graph write port, wired for ``publish`` and ``run``.
        gates: The human-gate policy, wired for ``publish`` and ``run``.
    """

    runs_root: Path
    specs: SpecLibrary
    config: HarnessConfig
    web: WebSourcePort | None = None
    llm: LLMPort | None = None
    repo: ContentGraphRepository | None = None
    gates: GatePolicy | None = None

    def workspace(self, run_id: str) -> RunWorkspace:
        """Resolve one run's file workspace.

        Args:
            run_id: The run's id (its workspace directory name).

        Returns:
            The bound workspace.
        """
        return RunWorkspace(self.runs_root / run_id)

    def require_web(self) -> WebSourcePort:
        """Return the wired web port, or fail loud if this command lacks one.

        Returns:
            The web-sourcing port.

        Raises:
            CliError: If no web port was injected.
        """
        if self.web is None:
            raise CliError("this command needs a web source port, which is not wired")
        return self.web

    def context(self, run_id: str) -> RunContext:
        """Assemble the full run context for the pipeline-driving commands.

        Fills the web slot with an unwired stand-in when absent (publish's
        re-wire never fetches), but demands the model, Content Graph, and gate
        ports the driving commands genuinely use.

        Args:
            run_id: The run's id.

        Returns:
            The assembled run context.

        Raises:
            CliError: If the model, Content Graph, or gate port is not wired.
        """
        if self.llm is None or self.repo is None or self.gates is None:
            raise CliError("this command needs the model, Content Graph, and gate ports wired")
        return RunContext(
            run_id=run_id,
            workspace=self.workspace(run_id),
            specs=self.specs,
            manifest=self.specs.manifest(),
            llm=self.llm,
            web=self.web if self.web is not None else _UNWIRED_WEB,
            repo=self.repo,
            gates=self.gates,
            config=self.config,
        )


def _violation_json(violation: Violation) -> dict[str, Any]:
    """Render one guardrail violation as a JSON-serializable object.

    Args:
        violation: The violation to render.

    Returns:
        Its ``code`` / ``subject`` / ``message`` / ``excerpt`` fields.
    """
    return {
        "code": violation.code,
        "subject": violation.subject,
        "message": violation.message,
        "excerpt": violation.excerpt,
    }


def _handle_check_piece(args: argparse.Namespace, deps: CliDeps) -> tuple[int, dict[str, Any]]:
    """Run the piece guardrails over one Piece deliverable.

    Args:
        args: The parsed arguments (``run_id``, ``piece_id``).
        deps: The injected dependencies.

    Returns:
        Exit 0 with an empty violations list when the Piece is clean; exit 1
        with the violation codes otherwise.
    """
    workspace = deps.workspace(args.run_id)
    piece = parse_piece(workspace.read(piece_path(args.piece_id)))
    violations = evaluate_piece(piece, deps.specs.banned_phrases())
    ok = not violations
    return (0 if ok else 1), {
        "command": "check-piece",
        "run_id": args.run_id,
        "piece_id": args.piece_id,
        "ok": ok,
        "violations": [_violation_json(violation) for violation in violations],
    }


def _handle_check_constellation(
    args: argparse.Namespace, deps: CliDeps
) -> tuple[int, dict[str, Any]]:
    """Assert the binary Tier-1 invariants (I1-I8) over a whole run.

    Args:
        args: The parsed arguments (``run_id``).
        deps: The injected dependencies.

    Returns:
        Exit 0 when every invariant holds; exit 1 with the failing invariant
        codes and their violations otherwise.
    """
    workspace = deps.workspace(args.run_id)
    constellation = constellation_from_workspace(workspace)
    report = evaluate_constellation(constellation, deps.specs.banned_phrases())
    return (0 if report.passed else 1), {
        "command": "check-constellation",
        "run_id": args.run_id,
        "ok": report.passed,
        "results": dict(report.results),
        "failed": list(report.failed_codes()),
        "violations": [_violation_json(violation) for violation in report.violations],
    }


def _handle_fetch(args: argparse.Namespace, deps: CliDeps) -> tuple[int, dict[str, Any]]:
    """Fetch one page's raw content and outlinks via the recall-first web port.

    Returns the page verbatim (no summarization) so the Researcher subagent can
    recall-then-fetch and citation-chase by following ``outlinks`` (ADR 0011).
    A navigation failure returns a null/again signal with a non-zero exit.

    Args:
        args: The parsed arguments (``url``).
        deps: The injected dependencies.

    Returns:
        Exit 0 with the fetched page; exit 2 with ``page: null`` when the URL
        could not be retrieved.
    """
    page = deps.require_web().fetch(args.url)
    if page is None:
        return 2, {"command": "fetch", "url": args.url, "ok": False, "page": None, "retry": True}
    return 0, {
        "command": "fetch",
        "url": args.url,
        "ok": True,
        "page": {
            "url": page.url,
            "content": page.content,
            "outlinks": list(page.outlinks),
            "fetched_at": page.fetched_at,
        },
    }


def _handle_verdict(args: argparse.Namespace, deps: CliDeps) -> tuple[int, dict[str, Any]]:
    """Record one human-gate verdict to ``feedback/verdicts.jsonl`` (ADR 0013).

    Resolves the manifest's gate, then appends via the shared ``record_verdict``
    — ``edit_approve`` is inferred from the machine->human diff, never passed,
    and a reject without a reason fails loud. This command is only a new
    front-end onto the unchanged verdict contract.

    Args:
        args: The parsed arguments (``run_id``, ``gate``, ``target``,
            ``approve``, ``reason``).
        deps: The injected dependencies.

    Returns:
        Exit 0 with the recorded verdict (``approve`` / ``edit_approve`` /
        ``reject``) and its diff.

    Raises:
        CliError: If the per-piece gate is missing its ``--target``.
    """
    gate = deps.specs.manifest().human_gate(args.gate)
    if gate.per_piece and not args.target:
        raise CliError(f"the {gate.name!r} gate needs --target <piece_id>")
    target_id = args.target if gate.per_piece else gate.name
    verdict = "approve" if args.approve else "reject"
    record = record_verdict(
        deps.workspace(args.run_id),
        gate,
        target_id,
        verdict,
        run_id=args.run_id,
        runtime=deps.config.runtime,
        model=deps.config.model,
        reason=args.reason or "",
    )
    return 0, {
        "command": "verdict",
        "run_id": args.run_id,
        "gate": gate.name,
        "target_id": target_id,
        "verdict": record.verdict,
        "reason": record.reason,
        "edit_diff": record.edit_diff,
    }


def _rejected_pieces(ctx: RunContext) -> set[str]:
    """The Piece ids the human rejected at the per-piece gate (latest verdict wins).

    Args:
        ctx: The run context.

    Returns:
        The rejected Piece ids drawn from ``feedback/verdicts.jsonl``.
    """
    latest: dict[str, str] = {}
    for record in read_verdicts(ctx.workspace):
        if record.gate == "piece":
            latest[record.target_id] = record.verdict
    return {target for target, verdict in latest.items() if verdict == "reject"}


def _handle_publish(args: argparse.Namespace, deps: CliDeps) -> tuple[int, dict[str, Any]]:
    """Re-wire, re-QA, and atomically write the approved survivor set (ADR 0012).

    Computes the survivors from the plan minus the pieces rejected in the
    verdict log, re-wires and re-QAs them, then — like the production graph's
    ``gate_constellation`` before ``write`` — refuses to write unless the
    constellation gate is approved, so neither runtime can publish a
    constellation the human has not ratified (ADR 0013, ADR 0019). Only the
    re-validated survivor set is written through the ``ContentGraphRepository``
    write port; a survivor that can never be made contract-valid raises out of
    re-QA (caught upstream); a survivor flagged while a valid set still writes
    is reported and the command exits non-zero so the operator sees it.

    Args:
        args: The parsed arguments (``run_id``).
        deps: The injected dependencies.

    Returns:
        Exit 0 when the whole survivor set published cleanly; exit 1 when some
        survivors were flagged back (only the re-validated set was written);
        exit 2 when the constellation gate is still pending or was rejected, in
        which case nothing is written (the rewired artifact is left for review).

    Raises:
        CliError: If every Piece was rejected, leaving nothing to publish.
    """
    ctx = deps.context(args.run_id)
    rejected = _rejected_pieces(ctx)
    survivors = frozenset(pid for pid in stages.load_plan(ctx).concept_ids() if pid not in rejected)
    if not survivors:
        raise CliError("every Piece was rejected; nothing to publish")
    publish.run_stage_rewire(ctx, survivors)
    validated, flagged = publish.run_stage_reqa(ctx, survivors)
    gate = deps.specs.manifest().human_gate("constellation")
    decision = preserve_and_decide(ctx.workspace, ctx.gates, gate, gate.name)
    if decision.status is not GateStatus.APPROVED:
        detail = (
            f"{gate.name} rejected: {decision.reason}"
            if decision.status is GateStatus.REJECTED
            else f"awaiting verdict at gate: {gate.name}"
        )
        return 2, {
            "command": "publish",
            "run_id": args.run_id,
            "ok": False,
            "status": str(decision.status),
            "detail": detail,
        }
    published = publish.run_stage_write(ctx, validated)
    ok = not flagged
    return (0 if ok else 1), {
        "command": "publish",
        "run_id": args.run_id,
        "ok": ok,
        "published": list(published),
        "flagged": sorted(flagged),
    }


def _handle_run(args: argparse.Namespace, deps: CliDeps) -> tuple[int, dict[str, Any]]:
    """Start or resume an in-process run, reporting where it paused (or published).

    Seeds ``goal.md`` from ``--brief`` on the first call, then runs the
    production engine to the next human gate. Re-invoking after a recorded
    verdict resumes off the on-disk deliverables (same semantics as the folded
    in ``scripts/gen.py`` driver).

    Args:
        args: The parsed arguments (``run_id``, optional ``brief``).
        deps: The injected dependencies.

    Returns:
        Exit 0 when the run paused or completed; exit 1 when it failed or was
        rejected.

    Raises:
        CliError: If the run is new and no ``--brief`` was given to seed it.
    """
    workspace = deps.workspace(args.run_id)
    if not workspace.exists(stages.GOAL):
        if not args.brief:
            raise CliError(f"run {args.run_id!r} is new — pass --brief to seed goal.md")
        workspace.write(stages.GOAL, args.brief)
    state = run_pipeline(deps.context(args.run_id))
    status = str(state.get("status", "running"))
    payload: dict[str, Any] = {
        "command": "run",
        "run_id": args.run_id,
        "status": status,
        "detail": str(state.get("detail", "")),
    }
    if "published" in state:
        payload["published"] = list(state["published"])
    ok = status not in {"failed", "rejected"}
    return (0 if ok else 1), payload


def _pending_gate(deps: CliDeps, workspace: RunWorkspace) -> str | None:
    """Find the first human gate still awaiting a verdict, read-only.

    Walks the three gates in fired order over the on-disk deliverables using
    the recorded verdicts — it never preserves a machine copy or mutates the
    workspace.

    Args:
        deps: The injected dependencies.
        workspace: The run's file workspace.

    Returns:
        A human-readable pending-gate label, or None if no gate is pending.
    """
    from harness.domain.plan import parse_plan

    manifest = deps.specs.manifest()
    gates = WorkspaceVerdictGates()
    plan_gate = manifest.human_gate("plan")
    if not workspace.exists(plan_gate.target):
        return None
    if gates.decide(workspace, plan_gate, "plan").status is GateStatus.PENDING:
        return "plan"
    try:
        plan = parse_plan(workspace.read(stages.PLAN))
    except HarnessError:
        return None
    piece_gate = manifest.human_gate("piece")
    for piece_id in plan.concept_ids():
        if workspace.exists(piece_gate.expand_target(piece_id)) and (
            gates.decide(workspace, piece_gate, piece_id).status is GateStatus.PENDING
        ):
            return f"piece {piece_id}"
    constellation_gate = manifest.human_gate("constellation")
    if workspace.exists(constellation_gate.target) and (
        gates.decide(workspace, constellation_gate, "constellation").status is GateStatus.PENDING
    ):
        return "constellation"
    return None


def _handle_status(args: argparse.Namespace, deps: CliDeps) -> tuple[int, dict[str, Any]]:
    """Report a run's current position read-only (last pending gate / completed).

    Args:
        args: The parsed arguments (``run_id``).
        deps: The injected dependencies.

    Returns:
        Exit 0 with the run's status and a human-readable detail; never mutates
        the workspace.
    """
    workspace = deps.workspace(args.run_id)
    if not workspace.exists(stages.GOAL):
        status, detail = "absent", "no goal.md — the run has not started"
    elif workspace.exists(publish.PUBLISH_RECEIPT):
        status, detail = "completed", "published — publish/published.json is present"
    else:
        pending = _pending_gate(deps, workspace)
        if pending is not None:
            status, detail = "paused", f"awaiting verdict at gate: {pending}"
        else:
            status, detail = "running", "no gate pending — run to advance"
    return 0, {"command": "status", "run_id": args.run_id, "status": status, "detail": detail}


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser and its subcommands.

    Returns:
        The configured parser; each subcommand sets a ``handler`` default.
    """
    parser = argparse.ArgumentParser(
        prog="harness",
        description="The shared generation-harness seam (ADR 0019).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check_piece = sub.add_parser(
        "check-piece", help="run the piece guardrails over one Piece deliverable"
    )
    check_piece.add_argument("run_id", help="the run's id (its workspace directory name)")
    check_piece.add_argument("piece_id", help="the Piece to check")
    check_piece.set_defaults(handler=_handle_check_piece)

    check_constellation = sub.add_parser(
        "check-constellation", help="assert the Tier-1 invariants I1-I8 over a run"
    )
    check_constellation.add_argument("run_id", help="the run's id")
    check_constellation.set_defaults(handler=_handle_check_constellation)

    fetch = sub.add_parser("fetch", help="fetch one URL's raw content + outlinks (recall-first)")
    fetch.add_argument("url", help="the URL to fetch")
    fetch.set_defaults(handler=_handle_fetch)

    verdict = sub.add_parser("verdict", help="record an approve/reject verdict at a human gate")
    verdict.add_argument("run_id", help="the run's id")
    verdict.add_argument(
        "--gate", required=True, choices=("plan", "piece", "constellation"), help="the gate acting"
    )
    verdict.add_argument("--target", default="", help="the Piece id (per-piece gate only)")
    decision = verdict.add_mutually_exclusive_group(required=True)
    decision.add_argument("--approve", action="store_true", help="approve the artifact")
    decision.add_argument("--reject", dest="approve", action="store_false", help="reject it")
    verdict.add_argument(
        "--reason", default="", help="required for a reject; the Distiller reads it"
    )
    verdict.set_defaults(handler=_handle_verdict)

    publish_cmd = sub.add_parser(
        "publish", help="re-wire, re-QA, and atomically write the approved survivors"
    )
    publish_cmd.add_argument("run_id", help="the run's id")
    publish_cmd.set_defaults(handler=_handle_publish)

    run_cmd = sub.add_parser("run", help="start or resume an in-process run to its next gate")
    run_cmd.add_argument("run_id", help="the run's id")
    run_cmd.add_argument("--brief", default="", help="the through-line; required on the first call")
    run_cmd.set_defaults(handler=_handle_run)

    status_cmd = sub.add_parser("status", help="report a run's current position (read-only)")
    status_cmd.add_argument("run_id", help="the run's id")
    status_cmd.set_defaults(handler=_handle_status)

    return parser


def _emit(stream: TextIO, payload: dict[str, Any]) -> None:
    """Write one structured result as pretty JSON.

    Args:
        stream: The output stream.
        payload: The result object.
    """
    stream.write(json.dumps(payload, indent=2) + "\n")


def run_cli(argv: Sequence[str], *, deps: CliDeps, stdout: TextIO | None = None) -> int:
    """Execute one subcommand over injected dependencies (the tested core).

    Parses ``argv``, dispatches to the subcommand handler, writes its
    structured JSON result to ``stdout``, and returns a process exit code.
    A :class:`~harness.errors.HarnessError` (a missing deliverable, a
    malformed artifact) is caught and reported as a structured error with a
    non-zero exit, so both the operator and the subagents can branch on it.

    Args:
        argv: The command-line arguments (without the program name).
        deps: The injected dependencies.
        stdout: Where to write the JSON result; ``sys.stdout`` by default.

    Returns:
        0 on success, 1 on a contract failure (violations), 2 on a usage or
        operational error.
    """
    stream = stdout if stdout is not None else sys.stdout
    parser = _build_parser()
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exit_signal:
        code = exit_signal.code
        return code if isinstance(code, int) else (0 if code is None else 1)
    exit_code: int
    payload: dict[str, Any]
    try:
        exit_code, payload = args.handler(args, deps)
    except HarnessError as error:
        exit_code, payload = 2, {"command": args.command, "ok": False, "error": str(error)}
    _emit(stream, payload)
    return exit_code


def _repo_root() -> Path:
    """The repository root holding the authored ``harness/`` specs and runs.

    Returns:
        The repo root (overridable via ``HARNESS_ROOT``).
    """
    return Path(__file__).resolve().parents[2]


def _env_config() -> HarnessConfig:
    """Resolve the run knobs from the environment for a real invocation.

    The ``runtime`` and ``model`` identity stamped on verdicts come from
    ``HARNESS_RUNTIME`` / ``HARNESS_MODEL`` when set, else from the resolved
    ``LLMConfig`` (the DeepSeek model identity), else a safe default — so a
    read-only command never requires the provider to be configured.

    Returns:
        The resolved config.
    """
    import os

    from harness.config import LLMConfig

    runtime = os.environ.get("HARNESS_RUNTIME", "").strip() or "langgraph"
    model = os.environ.get("HARNESS_MODEL", "").strip()
    if not model:
        try:
            llm_config = LLMConfig.from_env()
            model = f"{llm_config.provider}:{llm_config.precise.model}/{llm_config.creative.model}"
        except HarnessError:
            model = "unspecified"
    fan_out = int(os.environ.get("HARNESS_FAN_OUT", "") or 4)
    return HarnessConfig(runtime=runtime, model=model, fan_out=fan_out)


def _command_of(argv: Sequence[str]) -> str:
    """Peek the chosen subcommand from raw argv, before full parsing.

    Lets :func:`main` wire only the ports a command needs (the Playwright
    browser is built for ``fetch`` alone), rather than every adapter for a
    read-only check.

    Args:
        argv: The raw command-line arguments.

    Returns:
        The first positional token (the subcommand), or ``""`` if none.
    """
    return next((token for token in argv if not token.startswith("-")), "")


def main(argv: Sequence[str] | None = None) -> int:
    """Resolve the real adapters from the environment and run the core.

    Loads ``.env`` and wires the specs and run knobs from environment config
    exactly as ``build_app_from_env`` does for the API, then delegates to
    :func:`run_cli`. Heavy adapters are built only for the commands that use
    them (the Playwright web port for ``fetch``), so a read-only check needs no
    provider or database configured. No new secret surface (ADR 0019).

    Args:
        argv: The command-line arguments; ``sys.argv[1:]`` by default.

    Returns:
        The process exit code.
    """
    import os

    from dotenv import load_dotenv

    load_dotenv()
    raw = list(sys.argv[1:] if argv is None else argv)
    command = _command_of(raw)
    root = Path(os.environ.get("HARNESS_ROOT", "") or _repo_root())

    web: WebSourcePort | None = None
    closer: Callable[[], None] | None = None
    if command in {"fetch", "run"}:
        from harness.adapters.playwright_web import PlaywrightWebSource

        browser = PlaywrightWebSource()
        web, closer = browser, browser.close

    llm: LLMPort | None = None
    repo: ContentGraphRepository | None = None
    gates: GatePolicy | None = None
    if command in {"publish", "run"}:
        from content_graph.adapters.postgres import PostgresContentGraphRepository
        from content_graph.config import ContentGraphConfig
        from harness.adapters.llm_factory import build_llm
        from harness.config import LLMConfig

        llm = build_llm(LLMConfig.from_env())
        repo = PostgresContentGraphRepository.from_config(ContentGraphConfig.from_env())
        gates = WorkspaceVerdictGates()

    deps = CliDeps(
        runs_root=root / "harness" / "runs",
        specs=SpecLibrary(repo_root=root),
        config=_env_config(),
        web=web,
        llm=llm,
        repo=repo,
        gates=gates,
    )
    try:
        return run_cli(raw, deps=deps)
    finally:
        if closer is not None:
            closer()


if __name__ == "__main__":
    raise SystemExit(main())

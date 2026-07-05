"""In-process generation runs — dispatch off the request path, track state.

A generation run is minutes of LLM work; the admin trigger must return at once
and never wedge the reader endpoints (ADR 0015). This service owns that: it
records a run, hands the blocking work to a spawn seam (a background thread in
production), and lets the operator read the run's state back. It knows nothing
of the harness — the actual pipeline is an injected ``runner`` — so the
generation↔consumption boundary is a matter of who wires it, not what it
imports (ADR 0006).
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import uuid4

Runner = Callable[[str, str], object]
Spawn = Callable[[Callable[[], None]], None]


class RunState(StrEnum):
    """The lifecycle a triggered generation run moves through."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class RunRecord:
    """A triggered run's identity and current state.

    Attributes:
        run_id: The run's opaque handle, returned to the operator on trigger.
        state: Where the run is in its lifecycle.
        detail: A short explanation when a run fails; empty otherwise.
    """

    run_id: str
    state: RunState
    detail: str = ""


def _thread_spawn(thunk: Callable[[], None]) -> None:
    """Run a thunk on a daemon thread — the production dispatch."""
    threading.Thread(target=thunk, daemon=True).start()


class GenerationService:
    """Triggers, dispatches, and tracks in-process generation runs."""

    def __init__(
        self,
        runner: Runner,
        *,
        id_factory: Callable[[], str] | None = None,
        spawn: Spawn | None = None,
    ) -> None:
        """Wire the service to the pipeline runner and its dispatch strategy.

        Args:
            runner: Executes one run to completion (``run_id``, ``brief``);
                blocking. Raising marks the run failed.
            id_factory: Mints run ids; defaults to random UUIDs. Injectable so
                tests get deterministic handles.
            spawn: Dispatches the blocking run off the request path; defaults to
                a daemon thread. A synchronous spawn makes runs deterministic
                under test.
        """
        self._runner = runner
        self._new_run_id = id_factory or (lambda: uuid4().hex)
        self._spawn = spawn or _thread_spawn
        self._runs: dict[str, RunRecord] = {}
        self._lock = threading.Lock()

    def launch(self, brief: str) -> RunRecord:
        """Start a run and return its handle immediately (non-blocking).

        Args:
            brief: The through-line the Architect plans the constellation from.

        Returns:
            The run's record in the ``running`` state; the work proceeds off
            the request path.
        """
        run_id = self._new_run_id()
        self._store(RunRecord(run_id=run_id, state=RunState.RUNNING))
        self._spawn(lambda: self._execute(run_id, brief))
        return self._require(run_id)

    def get(self, run_id: str) -> RunRecord | None:
        """Return a run's current record, or None if the id is unknown.

        Args:
            run_id: The handle returned at trigger time.

        Returns:
            The run's record, or None.
        """
        with self._lock:
            return self._runs.get(run_id)

    def _execute(self, run_id: str, brief: str) -> None:
        """Run the pipeline, recording success or the failure's message.

        Any exception is caught and recorded as a failed run: a single bad run
        must never take the process — and the reader traffic it shares — down.
        """
        try:
            self._runner(run_id, brief)
        except Exception as exc:
            self._store(RunRecord(run_id=run_id, state=RunState.FAILED, detail=str(exc)))
            return
        self._store(replace(self._require(run_id), state=RunState.SUCCEEDED))

    def _store(self, record: RunRecord) -> None:
        """Persist a run record under its id."""
        with self._lock:
            self._runs[record.run_id] = record

    def _require(self, run_id: str) -> RunRecord:
        """Return a run record known to exist (set at launch time)."""
        with self._lock:
            return self._runs[run_id]

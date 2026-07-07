# 03 — `harness publish` + fold in `run` / `status`, delete `scripts/gen.py`

Status: ready-for-agent
Feature: claude-code-runtime

## Parent

PRD: [.scratch/claude-code-runtime/PRD.md](../PRD.md) · [ADR 0019](../../../docs/adr/0019-claude-code-generation-runtime-and-shared-harness-cli.md)

## What to build

The write side of the seam plus promoting the scratch in-process driver into the supported CLI.

- `harness publish <run_id>` — run the post-approval **rewire → reqa → atomic write** over the approved survivors ([ADR 0012](../../../docs/adr/0012-publish-gate-rewire-and-reqa-approved-subset.md)), writing only the re-validated survivor set through the `ContentGraphRepository` **write** port. A survivor that can't be made contract-valid is flagged back, never written into a broken state. Report the published set (or the flagged failures) as JSON.
- `harness run <run_id> [--brief "…"]` — start or resume an in-process run (production engine), writing `goal.md` on first call, and print where it paused (which gate) or that it published. Resumes off deliverables like the existing driver.
- `harness status <run_id>` — report the run's current position (last pending gate / completed) read-only.
- **Delete `scripts/gen.py`** once `run`/`status`/`verdict` cover its behavior; update any references.

## Acceptance criteria

- [ ] `harness publish <run>` over an approved fixture run writes the survivor set to the (in-memory, in test) `ContentGraphRepository` and reports it; a run with a rejected Piece publishes only the survivors and re-validates I4/I7 over them.
- [ ] A survivor that cannot be made contract-valid is reported as flagged and is **not** written; the command exits non-zero in that case.
- [ ] `harness run <new_run> --brief "…"` seeds `goal.md`, runs to the first gate, and reports the paused gate; re-invoking `harness run <run>` after a verdict resumes past it (same resume semantics as the current driver).
- [ ] `harness status <run>` reports the pending gate without mutating the workspace.
- [ ] `scripts/gen.py` is removed and nothing references it; the operator doc's driver section points at `harness run`.
- [ ] `tests/harness/test_cli.py` covers `publish` over the `fixture_run` substrate (approved-survivor write, rejected-Piece survivor subset, flagged-failure non-write); `ruff`, `mypy src`, `pytest` pass.

## Blocked by

- Issue 01 (the CLI core and test harness).

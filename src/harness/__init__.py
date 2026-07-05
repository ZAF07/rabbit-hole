"""The generation harness — the agentic pipeline that writes the Content Graph.

Generation-side only (ADR 0006): nothing here may depend on users, Sessions,
or any consumption concept. The harness's single output across the boundary
is Pieces, Connections, and Topic tags written through the
``ContentGraphRepository`` port; constellation, run id, Theme Brief, and
grounding ledger never cross.
"""

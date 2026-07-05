"""The HTTP API — the single backend deployable (ADR 0015).

One FastAPI application, the composition root that wires the reader use-cases
(and, later, the admin generation trigger) over their ports. Response DTOs
carry internal vocabulary only and only Pieces / Connections / Topics fields —
never a branded string, ``run_id``, or constellation (ADR 0001, ADR 0006).
"""

"""The consumption subsystem — the reader experience over the Content Graph.

Consumption reads *only* Pieces and Connections from the Content Graph and
knows nothing about runs, constellations, or how content was made (ADR 0006).
It adds the reader's own concerns — identity, the durable Session path, and the
Personal Knowledge Graph — none of which generation ever sees.
"""

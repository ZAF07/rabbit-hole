"""The Content Graph — the sole shared artifact between generation and consumption.

Generation writes Pieces, Connections, and Topics through the
``ContentGraphRepository`` port; consumption reads them through the same port.
Nothing else crosses the boundary (ADR 0006).
"""

"""The harness's two external tool seams, as ports (ADR 0011).

Every stage is file-in / file-out against the run workspace; only the LLM
and these two seams reach outside it. Fake both and the whole pipeline runs
offline and deterministically.
"""

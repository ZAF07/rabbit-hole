# The learning loop is human-ratified markdown compilation, not autonomous mutation

The content system improves over time by **compiling human editorial verdicts into the markdown artifacts the agents read** — Editorial DNA, the anti-slop guardrails, and labeled exemplars — **not** by any model retraining itself, and **not** by verdicts auto-rewriting those artifacts.

Two rules make this concrete:

1. **Learning changes files, not weights.** The "memory" that improves is version-controlled markdown + a labeled exemplar corpus, consistent with the harness principle that editing markdown changes behavior with no code change. Model fine-tuning / preference optimization is a *possible future* once the verdict corpus is large — explicitly **out of scope for V1**.
2. **Governed, batched distillation.** A distillation agent periodically *proposes* artifact changes (as a markdown diff) from accumulated human verdicts and edit-diffs; a **human ratifies each diff**. Verdicts never mutate the rubric, DNA, or exemplars autonomously. Cadence is batched (every N verdicts / periodic), not continuous.

**Why:**
- Keeps the human the arbiter of quality even over *how the system learns*. The one hard rule — AI must not decide editorial quality — is violated by an auto-updater that silently reshapes the bar.
- Autonomous self-learning content systems characteristically **rot**: the LLM judge is self-lenient, so unsupervised updates ratchet the bar *downward* toward the model's own slop. A human ratification step is the ratchet's pawl.
- Inspectable (you can read what was learned), reversible (git revert), and drift-proof.

**Trade-off:** slower to incorporate feedback than an autonomous loop, and it requires ongoing human ratification effort. Accepted — that human step *is* the moat, not overhead.

**Consequence:** calibration (per-Topic machine-vs-human agreement) gates only where the human *sampling* rate may relax; it never removes the human from ratifying artifact changes.

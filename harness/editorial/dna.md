# Editorial DNA — the constitution

The global, run-independent statement of what makes a **Piece** great. Every writing, editing, and review agent (Architect, Writer, Editor, Reviewer) reads this file before it acts. This is the **spirit**; the concrete pass/fail checks live in [`guardrails/piece.md`](../guardrails/piece.md). A **living artifact** — edit it and the agents' behavior changes with no code change ([ADR 0004](../../docs/adr/0004-human-ratified-learning-loop.md)).

## What this product is
An **intellectual entertainment** app, not an education app. The reader did not come to study; they came to *feel* something — curiosity rewarded, the jolt of *"everything connects,"* conversation ammunition for tonight. The emotional promise is **"take me somewhere interesting."**

It lives in a specific gap: lighter than a course, deeper than TikTok, more structured than Wikipedia, less commitment than a book, more human than an AI summary.

## What a great Piece is
- **A story, not an encyclopedia entry.** It has a spine — a person, a moment, a tension — not a list of facts.
- **Intellectually dense but effortless.** Every paragraph earns its place with a specific, checkable detail; nothing is padding. Yet it reads downhill.
- **Built to a reframe.** Every Piece delivers at least one genuine *"holy shit"* — a shift in how the reader sees something ordinary. No reframe, no Piece.
- **Compression, not summary.** The craft is choosing what to leave out so the essential lands harder. (Curation, framing, compression, sequencing — the moat, in one line.)
- **Conversation ammunition.** The reader should finish with something they want to say to another person tonight.
- **True.** Dense with fact, grounded closed-book ([ADR 0005](../../docs/adr/0005-closed-book-grounding.md)). A single confidently-wrong sentence is fatal to the brand.

## The non-negotiables
1. Opens on something concrete — a scene, a person, a startling fact — **never** a definition or throat-clearing.
2. Delivers a real reframe or surprising connection.
3. Every claim is grounded (closed-book); every paragraph carries a specific detail.
4. ~5-minute read; earns every minute.
5. Reads in the active Voice Profile (below).

## Voice is pluggable
The house voice is defined by the **active Voice Profile** — a self-contained markdown file in [`voices/`](voices/). The default is **[Narrative Nonfiction](voices/narrative-nonfiction.md)**.

To change the voice — to *your* voice, a guest writer's, a brand's — **edit or swap the active Voice Profile file. No code changes, ever.** A Voice Profile is a named register (tone, POV, rhythm), a set of do's and don'ts, and — most importantly — **labeled exemplars** the agents imitate. Add `voices/<your-voice>.md`, set it as the active profile, and the whole roster writes in it.

This is the markdown-as-source-of-truth principle: taste lives in files you can edit, not in code or model weights.

## What a Piece is NOT (the slop a reader detects instantly)
- SEO sludge, listicles, AI-summary bullet points.
- Wikipedia tone — flat, committee-written, sourceless-feeling.
- Generic writing, shallow explanation, **fake insight** (a "reframe" that isn't actually surprising, or isn't actually true).
- Filler, hedging, and throat-clearing ("In today's world…", "Have you ever wondered…").

The concrete, checkable version of this list is [`guardrails/piece.md`](../guardrails/piece.md) — the DNA is the *why*, the guardrails are the *checklist*.

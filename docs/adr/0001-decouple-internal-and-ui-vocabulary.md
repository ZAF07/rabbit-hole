# Decouple internal domain vocabulary from user-facing vocabulary

We maintain two separate vocabularies. The **internal** vocabulary — used everywhere in code, data model, content pipeline, and internal docs — is generic, obvious, and stable. The **UI/UX** vocabulary is an evocative "thread/weave" metaphor mapped onto it purely at the presentation surface. The app name is deliberately left unchosen.

| Internal (canonical) | UI/UX (branded) |
| --- | --- |
| Piece | Thread |
| Connection | Loose Thread / "Pull this thread" |
| Topic | Spool |
| Session | an Unspool |
| Personal Knowledge Graph | Tapestry |
| Daily Feature | Today's Thread |

**Why:** The naming that carries the most lock-in (what the code calls things) is settled first and independently of the naming that carries the least (what users see), which is deferred until we've built real content and can feel the emotional texture. We can rebrand, rename the app, or A/B-test surface language without touching a line of the data model or pipeline. It also forestalls a common mess where a marketing word ("Thread") quietly becomes an engineering identifier and can never be changed.

## The seam: a presentation vocabulary module

The decoupling lives in a single module — the app's **only** source of branded strings — structured as an i18n-style resource bundle. Internal terms are the keys; branded copy is the value.

```
// presentation/vocabulary — the single source of branded strings.
VOCABULARY = {
  appName:          "Unspool",                          // provisional
  piece:            { one: "Thread",       many: "Threads" },
  connection:       { one: "Loose Thread", many: "Loose Threads" },
  topic:            { one: "Spool",        many: "Spools" },
  session:          { noun: "Unspool", verb: "unspooling" },
  interestProfile:  "Tapestry",
  dailyFeature:     "Today's Thread",
  actions: { followConnection: "Pull this thread" },
}
```

- **UI code** renders from this bundle (`vocab.piece.one`) rather than hardcoding a branded literal.
- **Data model, API, and pipeline** never import it — they only know the internal terms.
- **To rebrand or rename the app:** edit this one file. To try an alternate brand voice: load an alternate bundle. Nothing else changes.
- **Exact location and format are provisional** until the tech stack is chosen; the recommended home is a single module at the presentation layer (e.g. `src/presentation/vocabulary.*`).

**Trade-off:** A small, ongoing translation cost between the two layers and the discipline of keeping the map current. The authoritative internal↔UI map lives in [`CONTEXT.md`](../../CONTEXT.md).

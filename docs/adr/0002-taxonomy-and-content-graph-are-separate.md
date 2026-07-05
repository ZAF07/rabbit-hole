# The Topic taxonomy and the Content Graph are two independent graphs

Content is organized by two separate structures that must never be conflated:

- **Topic taxonomy** — *classifies* content. Topics self-nest into a **DAG**: a Topic may have more than one parent (e.g. *Behavioral Economics* under both *Economics & Markets* and *Psychology*), so "category" and "subcategory" are just depths of one concept, not a strict tree. A Piece belongs to many Topics.
- **Content Graph** — the web of **Connections** between individual Pieces that users actually *traverse*.

**Connections are not constrained by the taxonomy.** A Connection may join Pieces in different Topics, and these **cross-Topic Connections — the surprising jumps — are the product's core value** ("everything connects"). The taxonomy exists to organize content, seed generation, drive onboarding, and render the Tapestry; it never fences the journey.

**Why this is recorded:**
- **Hard to reverse** — code that fences Connections inside a Topic, or stores Topic as a single-parent tree, is expensive to unwind once content and queries depend on it.
- **Surprising without context** — a future engineer will be tempted to "simplify" by making Connections respect Topic boundaries, or by giving each Topic exactly one parent. Both quietly destroy the core experience. This ADR exists to stop that.
- **Real trade-off** — a strict single-parent tree with Topic-bounded links is simpler to store, render, and reason about. We reject it because it lies about how knowledge actually relates and kills the cross-category magic.

**Consequence:** Topic is stored with zero-or-more parents (DAG). Connections carry no Topic constraint. The two graphs are queried and evolved independently.

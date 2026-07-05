CREATE TABLE topics (
    id    TEXT PRIMARY KEY,
    slug  TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL
);

CREATE TABLE topic_parents (
    child_id  TEXT NOT NULL REFERENCES topics (id) ON DELETE CASCADE,
    parent_id TEXT NOT NULL REFERENCES topics (id) ON DELETE CASCADE,
    PRIMARY KEY (child_id, parent_id),
    CHECK (child_id <> parent_id)
);

CREATE TABLE piece_topics (
    piece_id TEXT NOT NULL REFERENCES pieces (id) ON DELETE CASCADE,
    topic_id TEXT NOT NULL REFERENCES topics (id) ON DELETE CASCADE,
    PRIMARY KEY (piece_id, topic_id)
);

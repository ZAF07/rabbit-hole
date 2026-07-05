CREATE TABLE pieces (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    teaser        TEXT NOT NULL,
    read_time_min INTEGER NOT NULL CHECK (read_time_min >= 1),
    run_id        TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE blocks (
    id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    piece_id TEXT NOT NULL REFERENCES pieces (id) ON DELETE CASCADE,
    ordinal  INTEGER NOT NULL CHECK (ordinal >= 0),
    kind     TEXT NOT NULL CHECK (
        kind IN ('heading', 'paragraph', 'pull-quote', 'stat-callout', 'image', 'gif', 'diagram')
    ),
    payload  JSONB NOT NULL,
    UNIQUE (piece_id, ordinal)
);

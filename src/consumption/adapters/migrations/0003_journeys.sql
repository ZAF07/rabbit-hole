-- The durable path per User. Piece ids here are Content Graph ids, stored as
-- plain text with no foreign key: the reader's tables are a separate store and
-- must not reach across the boundary into the Content Graph (ADR 0006).

CREATE TABLE journeys (
    user_id    TEXT PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    stack      JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE journey_nodes (
    user_id  TEXT NOT NULL REFERENCES journeys (user_id) ON DELETE CASCADE,
    piece_id TEXT NOT NULL,
    ordinal  INTEGER NOT NULL CHECK (ordinal >= 0),
    PRIMARY KEY (user_id, piece_id),
    UNIQUE (user_id, ordinal)
);

CREATE TABLE journey_edges (
    user_id       TEXT NOT NULL REFERENCES journeys (user_id) ON DELETE CASCADE,
    from_piece_id TEXT NOT NULL,
    to_piece_id   TEXT NOT NULL,
    ordinal       INTEGER NOT NULL CHECK (ordinal >= 0),
    PRIMARY KEY (user_id, from_piece_id, to_piece_id),
    UNIQUE (user_id, ordinal)
);

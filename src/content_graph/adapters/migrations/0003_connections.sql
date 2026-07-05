CREATE TABLE connections (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    from_piece_id TEXT NOT NULL REFERENCES pieces (id) ON DELETE CASCADE,
    to_piece_id   TEXT NOT NULL REFERENCES pieces (id) ON DELETE CASCADE,
    hook          TEXT NOT NULL,
    UNIQUE (from_piece_id, to_piece_id),
    CHECK (from_piece_id <> to_piece_id)
);

CREATE INDEX connections_to_piece_id_idx ON connections (to_piece_id);

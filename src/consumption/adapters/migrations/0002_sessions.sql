CREATE TABLE sessions (
    id               TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    started_at       TIMESTAMPTZ NOT NULL,
    last_activity_at TIMESTAMPTZ NOT NULL,
    ended_at         TIMESTAMPTZ
);

CREATE INDEX sessions_user_recent ON sessions (user_id, started_at DESC);

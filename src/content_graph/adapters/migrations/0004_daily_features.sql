CREATE TABLE daily_features (
    date     DATE PRIMARY KEY,
    piece_id TEXT NOT NULL REFERENCES pieces (id) ON DELETE CASCADE
);

-- SQLite: INTEGER PRIMARY KEY, inline REFERENCES
CREATE TABLE playlists (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE tracks (
    id INTEGER PRIMARY KEY,
    playlist_id INTEGER NOT NULL REFERENCES playlists (id),
    title TEXT NOT NULL,
    duration_seconds INTEGER
);

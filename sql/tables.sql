CREATE TABLE IF NOT EXISTS trackers (
    id integer primary key,
    hash text not null,
    magnet text not null,
    title text not null,
    size text,
    body text
)
-- Schema of data/networking.db. Dates are YYYY-MM-DD.
-- version moves on with every change to a row, so a save from an older copy is refused
-- (writekit.rows.update_versioned). deleted_on hides someone or a talk deleted with undo: it is
-- never removed, and the read API and records.py leave it out. Someone deleted hides their talks.
-- Used by seed.py to create the database and by the tests to build fixtures. A change here is also
-- a new file in migrations/, which writer.py applies to the live database when it starts.

-- One row per person. id is a slug ("jane-doe") and is the page route: #/networking/jane-doe.
-- company and role are where they are now; about is who they are to you, in a line.
CREATE TABLE people (
    id        TEXT NOT NULL PRIMARY KEY CHECK (id GLOB '[a-z0-9]*' AND id NOT GLOB '*[^a-z0-9-]*'),
    name      TEXT NOT NULL,
    company   TEXT,
    role      TEXT,
    location  TEXT,
    met_how   TEXT,
    met_on    TEXT CHECK (met_on IS NULL OR met_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    linkedin  TEXT,
    email     TEXT,
    phone     TEXT,
    about     TEXT,
    version   INTEGER NOT NULL DEFAULT 1,
    deleted_on TEXT CHECK (deleted_on IS NULL OR deleted_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')
);

-- A company's website, once, for everyone there. people.company matches name; a company
-- with no row here just has no link.
CREATE TABLE companies (
    name     TEXT PRIMARY KEY,
    website  TEXT NOT NULL CHECK (website GLOB 'https://*')
);

-- Your own labels. A tag exists while at least one person has it.
CREATE TABLE person_tags (
    person_id  TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    tag        TEXT NOT NULL CHECK (tag <> ''),
    PRIMARY KEY (person_id, tag)
);

-- Every time they talked. notes are your own words after the talk, as you typed them, and are
-- never rewritten: summary is the short version. transcript only when the other person agreed
-- to be recorded.
-- next_step is what you do next, one of a fixed set and nothing more: the details live in
-- your messages. Only the latest interaction's next step is open; logging a new one closes the old.
CREATE TABLE interactions (
    id          INTEGER PRIMARY KEY,
    person_id   TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    date        TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    kind        TEXT NOT NULL CHECK (kind IN ('call', 'video', 'coffee', 'event', 'message', 'email')),
    title       TEXT,
    summary     TEXT,
    next_step   TEXT CHECK (next_step IN (
                    'follow-up', 'reach-out', 'catch-up', 'send-resume', 'ask-intro', 'schedule', 'share-work')),
    transcript  TEXT,
    notes       TEXT,
    version     INTEGER NOT NULL DEFAULT 1,
    deleted_on  TEXT CHECK (deleted_on IS NULL OR deleted_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')
);
CREATE INDEX interactions_person ON interactions(person_id, date);

-- The last migration in migrations/ this schema already includes; writer.py applies the rest.
PRAGMA user_version = 2;

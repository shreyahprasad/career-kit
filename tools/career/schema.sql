-- Schema of data/career.db. Dates are YYYY-MM-DD.
-- version moves on with every change to a row, so a save from an older copy is refused
-- (writekit.rows.update_versioned). deleted_on hides a role or event deleted with undo: it is
-- never removed, and the read API and records.py leave it out. A deleted role hides its events
-- and todos with it; a todo can also be deleted on its own.
-- Used by seed.py to create the database and by the tests to build fixtures. A change here is also
-- a new file in migrations/, which writer.py applies to the live database when it starts.

-- One row per role you are looking at or has applied to. id is a slug made from the company and
-- title ("lumen-labs-deployment-strategist") and is the page route: #/career/lumen-labs-deployment-strategist.
-- link is the posting; applied_via is where you applied, when that is somewhere else (a
-- referral portal, LinkedIn Easy Apply). comp is the band as the posting gives it, in words.
-- Key dates are on the timeline (events).
-- referral_person_id is an id in networking.db, kept as plain text: the career writer never
-- opens networking.db, and the read API looks up the name.
-- posting is the posting's text, read from its link when you added the role or pasted, since
-- postings come down when a role closes; posting_on is the day it was saved. notable is what
-- stands out in it, in your words: nothing written by AI is kept as fact.
-- resume_file is the PDF in data/resumes you mean to send; sent_file is the read-only copy of
-- it the writer keeps in data/sent when you apply, so the role always shows what that company
-- got. Both are file names only.
-- approved_resume_draft and approved_cover_letter are the drafts in data/drafts/<role> you approved
-- (resume-2.md, cover-letter-1.md). Applying keeps a read-only copy of the approved letter in
-- data/sent as sent_cover_letter, beside the resume's. Drafts are written by Claude; approving
-- one is yours.
CREATE TABLE roles (
    id                  TEXT NOT NULL PRIMARY KEY CHECK (id GLOB '[a-z0-9]*' AND id NOT GLOB '*[^a-z0-9-]*'),
    company             TEXT NOT NULL,
    title               TEXT NOT NULL,
    location            TEXT,
    link                TEXT CHECK (link IS NULL OR link GLOB 'https://*'),
    applied_via         TEXT CHECK (applied_via IS NULL OR applied_via GLOB 'https://*'),
    comp                TEXT,
    status              TEXT NOT NULL DEFAULT 'interested'
                            CHECK (status IN ('interested', 'applied', 'screen', 'interviews', 'offer', 'rejected')),
    referral_person_id  TEXT CHECK (referral_person_id IS NULL OR
                            (referral_person_id GLOB '[a-z0-9]*' AND referral_person_id NOT GLOB '*[^a-z0-9-]*')),
    resume_file         TEXT,
    sent_file           TEXT,
    approved_resume_draft TEXT,
    approved_cover_letter TEXT,
    sent_cover_letter   TEXT,
    notes               TEXT,
    posting             TEXT,
    posting_on          TEXT CHECK (posting_on IS NULL OR posting_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    notable             TEXT,
    version             INTEGER NOT NULL DEFAULT 1,
    deleted_on          TEXT CHECK (deleted_on IS NULL OR deleted_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')
);

-- The role's timeline: what happened and when. text is what you wrote about it; prep_link is
-- where your prep for it lives (a link or a path), when there is some.
CREATE TABLE events (
    id         INTEGER PRIMARY KEY,
    role_id    TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    date       TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    kind       TEXT NOT NULL CHECK (kind IN ('applied', 'recruiter-call', 'interview', 'offer', 'rejection', 'note')),
    text       TEXT,
    prep_link  TEXT,
    version    INTEGER NOT NULL DEFAULT 1,
    deleted_on TEXT CHECK (deleted_on IS NULL OR deleted_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')
);
CREATE INDEX events_role ON events(role_id, date);

-- What you have to do: for a role, or (role_id NULL) for your search as a whole. kind is the sort
-- of task, which colors it and lets you batch the same work. done_on is the day you checked it
-- off; NULL is still to do.
CREATE TABLE todos (
    id       INTEGER PRIMARY KEY,
    role_id  TEXT REFERENCES roles(id) ON DELETE CASCADE,
    text     TEXT NOT NULL,
    kind     TEXT NOT NULL DEFAULT 'other'
                 CHECK (kind IN ('resume', 'apply', 'outreach', 'prep', 'follow-up', 'other')),
    due_on   TEXT CHECK (due_on IS NULL OR due_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    done_on  TEXT CHECK (done_on IS NULL OR done_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    version  INTEGER NOT NULL DEFAULT 1,
    deleted_on TEXT CHECK (deleted_on IS NULL OR deleted_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')
);
CREATE INDEX todos_role ON todos(role_id);

-- The last migration in migrations/ this schema already includes; writer.py applies the rest.
PRAGMA user_version = 1;

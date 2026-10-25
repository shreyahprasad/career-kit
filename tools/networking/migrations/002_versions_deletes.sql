-- 2026-10-08: version moves on with every change, so a save from an older copy is refused;
-- deleted_on hides someone or a talk deleted with undo, never removing them.

ALTER TABLE people ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE people ADD COLUMN deleted_on TEXT CHECK (deleted_on IS NULL OR deleted_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]');
ALTER TABLE interactions ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE interactions ADD COLUMN deleted_on TEXT CHECK (deleted_on IS NULL OR deleted_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]');

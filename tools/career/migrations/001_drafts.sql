-- The drafts you approve for a role, and the copy of its cover letter kept when you apply.
ALTER TABLE roles ADD COLUMN approved_resume_draft TEXT;
ALTER TABLE roles ADD COLUMN approved_cover_letter TEXT;
ALTER TABLE roles ADD COLUMN sent_cover_letter TEXT;

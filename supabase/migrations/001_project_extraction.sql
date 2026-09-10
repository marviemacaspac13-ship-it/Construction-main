-- Stores the OCR read-quality report alongside the estimate: what the reader
-- saw (envelope, rooms, wall lengths), whether each dimension chain checksum
-- closed, its confidence, and any warnings it raised.
--
-- Optional. Without it estimates still save; the report is dropped on reload
-- and the Results screen shows the numbers without the caveats, which is
-- exactly the situation this column exists to prevent.
--
-- Run in the Supabase SQL editor.

ALTER TABLE projects ADD COLUMN IF NOT EXISTS extraction jsonb;

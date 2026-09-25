-- Each project belongs to the account that created it, and only that
-- account can see, change or delete it (audit finding AUTH-01).
--
-- Before this, `projects` had no owner column, so the only rule Supabase
-- could enforce was "any signed-in user, every row": every account saw and
-- could delete every other account's projects.
--
-- Run in the Supabase SQL editor, as one piece. It is a single transaction:
-- if any step fails - most likely the owner email below matching no account -
-- nothing is changed.
--
-- Projects created before this migration have no recorded owner. All of them
-- go to asd123@gmail.com, chosen by the owner on 25 Sep 2026; every other
-- account starts with none.

BEGIN;

-- 1. The owner column. New rows fill it from the session automatically, so
--    the app never has to send it - and cannot send someone else's.
ALTER TABLE public.projects
  ADD COLUMN IF NOT EXISTS user_id uuid
  REFERENCES auth.users (id) ON DELETE CASCADE
  DEFAULT auth.uid();

-- 2. Give the existing projects an owner.
UPDATE public.projects
SET user_id = (SELECT id FROM auth.users WHERE email = 'asd123@gmail.com')  -- chosen by the owner, 25 Sep 2026
WHERE user_id IS NULL;

-- Fails, and rolls everything back, if the email above matched no account.
ALTER TABLE public.projects ALTER COLUMN user_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS projects_user_id_idx ON public.projects (user_id);

-- 3. Replace every existing policy on the table. Policies are OR-ed, so
--    leaving an old "all signed-in users" policy in place would keep every
--    row visible no matter what is added below.
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT policyname FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'projects'
  LOOP
    EXECUTE format('DROP POLICY %I ON public.projects', r.policyname);
  END LOOP;
END $$;

ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;

-- `(select auth.uid())` rather than bare `auth.uid()` is Supabase's own
-- advice: it is evaluated once per query instead of once per row.
CREATE POLICY "projects: owner reads"   ON public.projects FOR SELECT TO authenticated
  USING (user_id = (select auth.uid()));

CREATE POLICY "projects: owner creates" ON public.projects FOR INSERT TO authenticated
  WITH CHECK (user_id = (select auth.uid()));

CREATE POLICY "projects: owner updates" ON public.projects FOR UPDATE TO authenticated
  USING (user_id = (select auth.uid()))
  WITH CHECK (user_id = (select auth.uid()));

CREATE POLICY "projects: owner deletes" ON public.projects FOR DELETE TO authenticated
  USING (user_id = (select auth.uid()));

COMMIT;

-- Check afterwards (should list exactly the four policies above):
--   SELECT policyname, cmd FROM pg_policies WHERE tablename = 'projects';

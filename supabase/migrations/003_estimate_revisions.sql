-- Requires 001_project_extraction.sql and 002_project_owner.sql.
-- Deploy with the backend save feature disabled; see ../REVISION_DEPLOYMENT.md.
BEGIN;

ALTER TABLE public.projects ADD COLUMN active_revision_id uuid;

CREATE TABLE public.plan_assets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
  created_by uuid NOT NULL REFERENCES auth.users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
  original_filename text NOT NULL CHECK (length(original_filename) BETWEEN 1 AND 255),
  media_type text NOT NULL CHECK (media_type IN ('image/png', 'image/jpeg', 'image/webp')),
  byte_size bigint NOT NULL CHECK (byte_size > 0),
  -- Metadata foundation only. Private file upload/viewing is TODO task 4.
  storage_path text UNIQUE,
  UNIQUE (project_id, id)
);

CREATE TABLE public.scan_revisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
  asset_id uuid NOT NULL,
  created_by uuid NOT NULL REFERENCES auth.users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  original_input jsonb NOT NULL CHECK (jsonb_typeof(original_input) = 'object'),
  scan jsonb NOT NULL CHECK (jsonb_typeof(scan) = 'object'),
  extraction jsonb,
  unmatched_detections jsonb NOT NULL CHECK (jsonb_typeof(unmatched_detections) = 'array'),
  UNIQUE (project_id, id),
  FOREIGN KEY (project_id, asset_id) REFERENCES public.plan_assets(project_id, id)
);

CREATE TABLE public.estimate_revisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
  scan_revision_id uuid NOT NULL,
  parent_revision_id uuid,
  created_by uuid NOT NULL REFERENCES auth.users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  corrections jsonb NOT NULL,
  effective_input jsonb NOT NULL CHECK (jsonb_typeof(effective_input) = 'object'),
  estimate jsonb NOT NULL CHECK (jsonb_typeof(estimate) = 'object'),
  idempotency_key uuid NOT NULL,
  -- Keep the full normalised request, not just a hash: collision-free retry comparison.
  save_request jsonb NOT NULL,
  UNIQUE (project_id, id),
  UNIQUE (project_id, idempotency_key),
  FOREIGN KEY (project_id, scan_revision_id) REFERENCES public.scan_revisions(project_id, id),
  FOREIGN KEY (project_id, parent_revision_id) REFERENCES public.estimate_revisions(project_id, id)
);

ALTER TABLE public.projects ADD CONSTRAINT projects_active_revision_fk
  FOREIGN KEY (id, active_revision_id)
  REFERENCES public.estimate_revisions(project_id, id) DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX plan_assets_project_idx ON public.plan_assets(project_id);
CREATE INDEX scan_revisions_project_idx ON public.scan_revisions(project_id);
CREATE INDEX estimate_revisions_project_idx ON public.estimate_revisions(project_id, created_at);

ALTER TABLE public.plan_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scan_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.estimate_revisions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "plan assets: owner reads" ON public.plan_assets FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.projects p WHERE p.id = project_id AND p.user_id = (select auth.uid())));
CREATE POLICY "scan revisions: owner reads" ON public.scan_revisions FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.projects p WHERE p.id = project_id AND p.user_id = (select auth.uid())));
CREATE POLICY "estimate revisions: owner reads" ON public.estimate_revisions FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.projects p WHERE p.id = project_id AND p.user_id = (select auth.uid())));

REVOKE ALL ON public.plan_assets, public.scan_revisions, public.estimate_revisions FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON public.plan_assets, public.scan_revisions, public.estimate_revisions TO authenticated;

-- Even the service writer cannot rewrite history. Deleting a whole project
-- still cascades through its revisions under the existing owner delete policy.
CREATE FUNCTION public.reject_revision_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN
  RAISE EXCEPTION 'revision records are immutable' USING ERRCODE = '55000';
END;
$$;
CREATE TRIGGER immutable_asset BEFORE UPDATE ON public.plan_assets
  FOR EACH ROW EXECUTE FUNCTION public.reject_revision_update();
CREATE TRIGGER immutable_scan BEFORE UPDATE ON public.scan_revisions
  FOR EACH ROW EXECUTE FUNCTION public.reject_revision_update();
CREATE TRIGGER immutable_estimate BEFORE UPDATE ON public.estimate_revisions
  FOR EACH ROW EXECUTE FUNCTION public.reject_revision_update();

-- Do not permit a browser to bypass CAS by changing the pointer or summaries.
REVOKE INSERT, UPDATE ON public.projects FROM PUBLIC, anon, authenticated;
GRANT INSERT (name, description, plan_type, status) ON public.projects TO authenticated;
GRANT UPDATE (name, description) ON public.projects TO authenticated;

CREATE FUNCTION public.save_scan_estimate(
  p_owner uuid, p_project_id uuid, p_expected_active_revision_id uuid,
  p_idempotency_key uuid, p_result jsonb, p_asset jsonb
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE
  v_project public.projects;
  v_existing public.estimate_revisions;
  v_request jsonb;
  v_asset uuid;
  v_scan uuid;
  v_revision uuid;
BEGIN
  -- Only FastAPI's service-role RPC can execute this function. p_owner is
  -- derived from its checked bearer token, never from the request body.
  SELECT * INTO v_project FROM public.projects
    WHERE id = p_project_id AND user_id = p_owner FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'project not found' USING ERRCODE = 'P0002';
  END IF;
  IF p_idempotency_key IS NULL THEN
    RAISE EXCEPTION 'idempotency key required' USING ERRCODE = '22023';
  END IF;
  v_request := jsonb_build_object('result', p_result, 'asset', p_asset,
    'expected_active_revision_id', p_expected_active_revision_id);
  SELECT * INTO v_existing FROM public.estimate_revisions
    WHERE project_id = p_project_id AND idempotency_key = p_idempotency_key;
  IF FOUND THEN
    IF v_existing.save_request IS DISTINCT FROM v_request THEN
      RAISE EXCEPTION 'idempotency key reused with different content' USING ERRCODE = '23505';
    END IF;
    RETURN v_existing.id;
  END IF;
  IF v_project.active_revision_id IS DISTINCT FROM p_expected_active_revision_id THEN
    RAISE EXCEPTION 'active revision changed; reopen the project before saving' USING ERRCODE = '40001';
  END IF;
  IF (p_result #>> '{original_input,schema_version}') IS DISTINCT FROM '1'
    OR (p_result #>> '{estimate,plan_type}') IS DISTINCT FROM v_project.plan_type
    OR (p_result #>> '{original_input,plan,plan_type}') IS DISTINCT FROM v_project.plan_type
    OR (p_result #>> '{original_input,rules_version}') IS DISTINCT FROM (p_result #>> '{estimate,rules_version}')
    OR (p_asset ->> 'source_sha256') IS DISTINCT FROM (p_result #>> '{scan,source_sha256}')
  THEN
    RAISE EXCEPTION 'inconsistent estimate input' USING ERRCODE = '22023';
  END IF;

  INSERT INTO public.plan_assets(project_id, created_by, source_sha256, original_filename, media_type, byte_size)
  VALUES (p_project_id, p_owner, p_asset ->> 'source_sha256', p_asset ->> 'original_filename',
    p_asset ->> 'media_type', (p_asset ->> 'byte_size')::bigint) RETURNING id INTO v_asset;
  INSERT INTO public.scan_revisions(project_id, asset_id, created_by, original_input, scan, extraction, unmatched_detections)
  VALUES (p_project_id, v_asset, p_owner, p_result -> 'original_input', p_result -> 'scan',
    NULLIF(p_result -> 'extraction', 'null'::jsonb), p_result -> 'unmatched_detections') RETURNING id INTO v_scan;
  INSERT INTO public.estimate_revisions(project_id, scan_revision_id, parent_revision_id, created_by,
    corrections, effective_input, estimate, idempotency_key, save_request)
  VALUES (p_project_id, v_scan, p_expected_active_revision_id, p_owner,
    '{"quantities":{},"unit_prices":{},"reason":null}'::jsonb,
    p_result -> 'original_input', p_result -> 'estimate', p_idempotency_key, v_request)
    RETURNING id INTO v_revision;
  UPDATE public.projects SET active_revision_id = v_revision, status = 'completed', error_message = NULL,
    grand_total = (p_result #>> '{estimate,grand_total}')::numeric,
    line_items = p_result #> '{estimate,line_items}',
    unmatched_detections = p_result -> 'unmatched_detections',
    extraction = NULLIF(p_result -> 'extraction', 'null'::jsonb), updated_at = now()
  WHERE id = p_project_id;
  RETURN v_revision;
END;
$$;
REVOKE ALL ON FUNCTION public.save_scan_estimate(uuid, uuid, uuid, uuid, jsonb, jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.save_scan_estimate(uuid, uuid, uuid, uuid, jsonb, jsonb) TO service_role;

CREATE FUNCTION public.record_scan_failure(p_owner uuid, p_project_id uuid, p_message text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
  -- A failed retry never hides a previously completed result.
  UPDATE public.projects SET status = 'error', error_message = left(p_message, 2000), updated_at = now()
  WHERE id = p_project_id AND user_id = p_owner AND active_revision_id IS NULL AND status <> 'completed';
END;
$$;
REVOKE ALL ON FUNCTION public.record_scan_failure(uuid, uuid, text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_scan_failure(uuid, uuid, text) TO service_role;
COMMIT;

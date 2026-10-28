-- Requires 001-004. Deploy before enabling PLAN_ASSETS_ENABLED.
BEGIN;
INSERT INTO storage.buckets(id, name, public, file_size_limit, allowed_mime_types)
VALUES ('trace-plans', 'trace-plans', false, 26214400, ARRAY['image/png','image/jpeg','image/webp'])
ON CONFLICT (id) DO UPDATE SET public=false, file_size_limit=26214400,
  allowed_mime_types=EXCLUDED.allowed_mime_types;
-- Backend-only object access. This also constrains any pre-existing broad policy.
CREATE POLICY "TRACE original plans: backend only" ON storage.objects AS RESTRICTIVE
  FOR ALL TO anon, authenticated USING (bucket_id <> 'trace-plans')
  WITH CHECK (bucket_id <> 'trace-plans');

ALTER TABLE public.plan_assets ADD COLUMN pixel_width integer CHECK (pixel_width > 0);
ALTER TABLE public.plan_assets ADD COLUMN pixel_height integer CHECK (pixel_height > 0);
CREATE TABLE public.plan_uploads (
  id uuid PRIMARY KEY,
  project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
  owner_id uuid NOT NULL REFERENCES auth.users(id),
  metadata jsonb NOT NULL,
  storage_path text NOT NULL UNIQUE,
  state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','ready','deleting')),
  touched_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.plan_file_cleanup (
  storage_path text PRIMARY KEY,
  owner_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.plan_uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.plan_file_cleanup ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.plan_uploads, public.plan_file_cleanup FROM PUBLIC, anon, authenticated, service_role;

CREATE FUNCTION public.begin_plan_upload(p_owner uuid, p_project_id uuid, p_upload_id uuid, p_metadata jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE v_upload public.plan_uploads; v_path text; v_ext text;
BEGIN
  -- Serialize with project deletion and revision saving.
  PERFORM 1 FROM public.projects WHERE id=p_project_id AND user_id=p_owner FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'project not found' USING ERRCODE='P0002'; END IF;
  IF p_upload_id IS NULL OR (p_metadata->>'source_sha256') !~ '^[0-9a-f]{64}$'
    OR (p_metadata->>'byte_size')::bigint NOT BETWEEN 1 AND 26214400
    OR (p_metadata->>'pixel_width')::bigint * (p_metadata->>'pixel_height')::bigint NOT BETWEEN 1 AND 40000000
    OR (p_metadata->>'pixel_width')::bigint <= 0 OR (p_metadata->>'pixel_height')::bigint <= 0
    OR length(p_metadata->>'original_filename') NOT BETWEEN 1 AND 255
    OR NOT (p_metadata ?& ARRAY['source_sha256','byte_size','pixel_width','pixel_height','original_filename','media_type'])
  THEN RAISE EXCEPTION 'invalid image metadata' USING ERRCODE='22023'; END IF;
  v_ext := CASE p_metadata->>'media_type' WHEN 'image/png' THEN 'png'
    WHEN 'image/jpeg' THEN 'jpg' WHEN 'image/webp' THEN 'webp' END;
  IF v_ext IS NULL THEN RAISE EXCEPTION 'unsupported image' USING ERRCODE='22023'; END IF;
  v_path := p_owner::text || '/' || p_project_id::text || '/' || p_upload_id::text || '/original.' || v_ext;
  INSERT INTO public.plan_uploads(id,project_id,owner_id,metadata,storage_path)
    VALUES(p_upload_id,p_project_id,p_owner,p_metadata,v_path) ON CONFLICT(id) DO NOTHING;
  SELECT * INTO v_upload FROM public.plan_uploads WHERE id=p_upload_id FOR UPDATE;
  IF v_upload.owner_id IS DISTINCT FROM p_owner OR v_upload.project_id IS DISTINCT FROM p_project_id
    OR v_upload.metadata IS DISTINCT FROM p_metadata OR v_upload.state='deleting'
  THEN RAISE EXCEPTION 'upload conflict' USING ERRCODE='PT409'; END IF;
  UPDATE public.plan_uploads SET touched_at=now() WHERE id=p_upload_id;
  RETURN jsonb_build_object('storage_path',v_upload.storage_path,'state',v_upload.state);
END; $$;

CREATE FUNCTION public.finish_plan_upload(p_owner uuid, p_project_id uuid, p_upload_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE v_upload public.plan_uploads; v_asset public.plan_assets;
BEGIN
  PERFORM 1 FROM public.projects WHERE id=p_project_id AND user_id=p_owner FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'project not found' USING ERRCODE='P0002'; END IF;
  SELECT * INTO v_upload FROM public.plan_uploads
    WHERE id=p_upload_id AND project_id=p_project_id AND owner_id=p_owner FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'upload not found' USING ERRCODE='P0002'; END IF;
  IF v_upload.state='deleting' THEN RAISE EXCEPTION 'upload expired' USING ERRCODE='PT409'; END IF;
  INSERT INTO public.plan_assets(id,project_id,created_by,source_sha256,original_filename,media_type,
    byte_size,storage_path,pixel_width,pixel_height)
  VALUES(p_upload_id,p_project_id,p_owner,v_upload.metadata->>'source_sha256',
    v_upload.metadata->>'original_filename',v_upload.metadata->>'media_type',
    (v_upload.metadata->>'byte_size')::bigint,v_upload.storage_path,
    (v_upload.metadata->>'pixel_width')::integer,(v_upload.metadata->>'pixel_height')::integer)
  ON CONFLICT(id) DO NOTHING;
  UPDATE public.plan_uploads SET state='ready',touched_at=now() WHERE id=p_upload_id;
  SELECT * INTO v_asset FROM public.plan_assets WHERE id=p_upload_id;
  RETURN to_jsonb(v_asset);
END; $$;

CREATE FUNCTION public.owned_plan_asset(p_owner uuid, p_project_id uuid, p_asset_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE v_asset public.plan_assets;
BEGIN
  SELECT a.* INTO v_asset FROM public.plan_assets a JOIN public.projects p ON p.id=a.project_id
    WHERE p.user_id=p_owner AND p.id=p_project_id AND a.id=p_asset_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'plan not found' USING ERRCODE='P0002'; END IF;
  RETURN to_jsonb(v_asset);
END; $$;

-- Deleting a project queues its objects; retrying cleanup cannot delete linked history.
CREATE FUNCTION public.queue_plan_file_cleanup() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$ BEGIN
  INSERT INTO public.plan_file_cleanup(storage_path,owner_id)
    VALUES(OLD.storage_path,OLD.owner_id) ON CONFLICT DO NOTHING;
  RETURN OLD;
END; $$;
CREATE TRIGGER queue_deleted_plan_file AFTER DELETE ON public.plan_uploads
  FOR EACH ROW EXECUTE FUNCTION public.queue_plan_file_cleanup();

CREATE FUNCTION public.claim_plan_file_cleanup(p_owner uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE v_paths jsonb;
BEGIN
  -- Only incomplete uploads expire. Ready files include refused scans and are retained.
  UPDATE public.plan_uploads SET state='deleting'
    WHERE owner_id=p_owner AND state='pending' AND touched_at < now()-interval '24 hours';
  SELECT coalesce(jsonb_agg(storage_path),'[]'::jsonb) INTO v_paths FROM (
    SELECT storage_path FROM public.plan_uploads WHERE owner_id=p_owner AND state='deleting'
    UNION SELECT storage_path FROM public.plan_file_cleanup
      WHERE owner_id=p_owner AND created_at < now()-interval '24 hours'
    LIMIT 100
  ) candidates;
  RETURN v_paths;
END; $$;

-- Maintenance CLI can drain queues for owners who do not return to the browser.
CREATE FUNCTION public.plan_cleanup_owners() RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path='' AS $$
  SELECT coalesce(jsonb_agg(owner_id),'[]'::jsonb) FROM (
    SELECT owner_id FROM public.plan_uploads WHERE state='deleting'
      OR (state='pending' AND touched_at < now()-interval '24 hours')
    UNION SELECT owner_id FROM public.plan_file_cleanup WHERE created_at < now()-interval '24 hours'
  ) owners;
$$;
CREATE FUNCTION public.finish_plan_file_cleanup(p_owner uuid,p_path text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$ BEGIN
  DELETE FROM public.plan_uploads WHERE owner_id=p_owner AND storage_path=p_path AND state='deleting';
  DELETE FROM public.plan_file_cleanup WHERE owner_id=p_owner AND storage_path=p_path;
  RETURN true;
END; $$;

REVOKE ALL ON FUNCTION public.begin_plan_upload(uuid,uuid,uuid,jsonb),
  public.finish_plan_upload(uuid,uuid,uuid),public.owned_plan_asset(uuid,uuid,uuid),
  public.claim_plan_file_cleanup(uuid),public.finish_plan_file_cleanup(uuid,text),
  public.plan_cleanup_owners(),
  public.queue_plan_file_cleanup() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.begin_plan_upload(uuid,uuid,uuid,jsonb),
  public.finish_plan_upload(uuid,uuid,uuid),public.owned_plan_asset(uuid,uuid,uuid),
  public.claim_plan_file_cleanup(uuid),public.finish_plan_file_cleanup(uuid,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.plan_cleanup_owners() TO service_role;

-- save_scan_estimate is replaced below with the existing CAS/idempotency contract.

CREATE OR REPLACE FUNCTION public.save_scan_estimate(
  p_owner uuid, p_project_id uuid, p_expected_active_revision_id uuid,
  p_idempotency_key uuid, p_result jsonb, p_asset jsonb
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE
  v_project public.projects;
  v_existing public.estimate_revisions;
  v_request jsonb;
  v_asset uuid;
  v_stored public.plan_assets;
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
    RAISE EXCEPTION 'active revision changed; reopen the project before saving' USING ERRCODE = 'PT409';
  END IF;
  IF (p_result #>> '{original_input,schema_version}') IS DISTINCT FROM '1'
    OR (p_result #>> '{estimate,plan_type}') IS DISTINCT FROM v_project.plan_type
    OR (p_result #>> '{original_input,plan,plan_type}') IS DISTINCT FROM v_project.plan_type
    OR (p_result #>> '{original_input,rules_version}') IS DISTINCT FROM (p_result #>> '{estimate,rules_version}')
    OR (p_asset ->> 'source_sha256') IS DISTINCT FROM (p_result #>> '{scan,source_sha256}')
  THEN
    RAISE EXCEPTION 'inconsistent estimate input' USING ERRCODE = '22023';
  END IF;

  IF p_asset->>'asset_id' IS NOT NULL THEN
    SELECT * INTO v_stored FROM public.plan_assets WHERE id=(p_asset->>'asset_id')::uuid
      AND project_id=p_project_id AND created_by=p_owner AND storage_path IS NOT NULL;
    IF NOT FOUND THEN RAISE EXCEPTION 'stored plan not found' USING ERRCODE='P0002'; END IF;
    IF v_stored.source_sha256 IS DISTINCT FROM (p_asset->>'source_sha256')
      OR v_stored.byte_size IS DISTINCT FROM (p_asset->>'byte_size')::bigint
      OR v_stored.media_type IS DISTINCT FROM (p_asset->>'media_type')
      OR v_stored.original_filename IS DISTINCT FROM (p_asset->>'original_filename')
    THEN RAISE EXCEPTION 'asset differs from scan' USING ERRCODE='22023'; END IF;
    v_asset := v_stored.id;
  ELSE
    -- Compatibility for historical clients; current UI always supplies a stored asset.
    INSERT INTO public.plan_assets(project_id, created_by, source_sha256, original_filename, media_type, byte_size)
    VALUES (p_project_id, p_owner, p_asset ->> 'source_sha256', p_asset ->> 'original_filename',
      p_asset ->> 'media_type', (p_asset ->> 'byte_size')::bigint) RETURNING id INTO v_asset;
  END IF;
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

COMMIT;


-- Requires migration 003. Preserve all history, grants and owner checks.
-- Stale preconditions are application conflicts, not database serialization failures.
-- PT409 tells PostgREST to return an explicit non-retryable HTTP 409.
BEGIN;
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

COMMIT;


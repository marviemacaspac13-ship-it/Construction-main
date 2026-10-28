-- Requires 003–005. Owner checks are explicit because only the service role calls these.
BEGIN;
CREATE FUNCTION public.owned_estimate_scan(p_owner uuid, p_project_id uuid, p_scan_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE v_scan public.scan_revisions;
BEGIN
  SELECT s.* INTO v_scan FROM public.scan_revisions s JOIN public.projects p ON p.id=s.project_id
    WHERE p.id=p_project_id AND p.user_id=p_owner AND s.id=p_scan_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'scan not found' USING ERRCODE='P0002'; END IF;
  RETURN to_jsonb(v_scan);
END; $$;

CREATE FUNCTION public.manual_estimate_context(p_owner uuid, p_project_id uuid, p_asset_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE v_asset jsonb; v_type text;
BEGIN
  v_asset := public.owned_plan_asset(p_owner,p_project_id,p_asset_id);
  SELECT plan_type INTO v_type FROM public.projects WHERE id=p_project_id AND user_id=p_owner;
  RETURN jsonb_build_object('asset',v_asset,'plan_type',v_type);
END; $$;

CREATE FUNCTION public.save_corrected_estimate(
  p_owner uuid, p_project_id uuid, p_scan_id uuid, p_expected_active_revision_id uuid,
  p_idempotency_key uuid, p_corrections jsonb, p_effective_input jsonb, p_estimate jsonb
) RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE v_project public.projects; v_scan public.scan_revisions;
  v_existing public.estimate_revisions; v_request jsonb; v_id uuid;
BEGIN
  SELECT * INTO v_project FROM public.projects WHERE id=p_project_id AND user_id=p_owner FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'project not found' USING ERRCODE='P0002'; END IF;
  IF p_idempotency_key IS NULL THEN RAISE EXCEPTION 'key required' USING ERRCODE='22023'; END IF;
  SELECT * INTO v_scan FROM public.scan_revisions WHERE id=p_scan_id AND project_id=p_project_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'scan not found' USING ERRCODE='P0002'; END IF;
  -- Calculation timestamps vary on retries. Compare the request, not server output.
  v_request := jsonb_build_object('kind','correction','scan_id',p_scan_id,
    'expected_active_revision_id',p_expected_active_revision_id,'corrections',p_corrections);
  SELECT * INTO v_existing FROM public.estimate_revisions WHERE project_id=p_project_id AND idempotency_key=p_idempotency_key;
  IF FOUND THEN
    IF v_existing.save_request IS DISTINCT FROM v_request THEN
      RAISE EXCEPTION 'key reused' USING ERRCODE='23505';
    END IF;
    RETURN v_existing.id;
  END IF;
  IF v_project.active_revision_id IS DISTINCT FROM p_expected_active_revision_id
    OR NOT EXISTS (SELECT 1 FROM public.estimate_revisions WHERE id=p_expected_active_revision_id
                   AND project_id=p_project_id AND scan_revision_id=p_scan_id) THEN
    RAISE EXCEPTION 'revision changed' USING ERRCODE='PT409';
  END IF;
  IF p_effective_input#>>'{plan,plan_type}' IS DISTINCT FROM v_project.plan_type
    OR p_estimate->>'plan_type' IS DISTINCT FROM v_project.plan_type
    OR p_effective_input->>'rules_version' IS DISTINCT FROM p_estimate->>'rules_version'
    OR p_effective_input->>'schema_version' IS DISTINCT FROM '1' THEN
    RAISE EXCEPTION 'invalid estimate' USING ERRCODE='22023';
  END IF;
  INSERT INTO public.estimate_revisions(project_id,scan_revision_id,parent_revision_id,created_by,
    corrections,effective_input,estimate,idempotency_key,save_request)
  VALUES(p_project_id,p_scan_id,p_expected_active_revision_id,p_owner,p_corrections,p_effective_input,
    p_estimate,p_idempotency_key,v_request) RETURNING id INTO v_id;
  UPDATE public.projects SET active_revision_id=v_id,status='completed',error_message=NULL,
    grand_total=(p_estimate->>'grand_total')::numeric,line_items=p_estimate->'line_items',
    extraction=v_scan.extraction,unmatched_detections=v_scan.unmatched_detections,updated_at=now()
    WHERE id=p_project_id;
  RETURN v_id;
END; $$;
REVOKE ALL ON FUNCTION public.owned_estimate_scan(uuid,uuid,uuid), public.manual_estimate_context(uuid,uuid,uuid),
 public.save_corrected_estimate(uuid,uuid,uuid,uuid,uuid,jsonb,jsonb,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.owned_estimate_scan(uuid,uuid,uuid), public.manual_estimate_context(uuid,uuid,uuid),
 public.save_corrected_estimate(uuid,uuid,uuid,uuid,uuid,jsonb,jsonb,jsonb) TO service_role;
COMMIT;

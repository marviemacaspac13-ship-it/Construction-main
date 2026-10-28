import { authHeaders, supabase } from "./supabase";
import type { ScanResult } from "./scan";
import type { ExtractionReport, ImageEstimate, PricedLine } from "./estimate";
import type { EstimateRevision } from "./estimate-input";
import { submitEstimateSave, type PendingEstimateSave } from "./revision-save";
import { cleanupPlanFiles, type PlanAsset } from "./plan-assets";

const API_URL = import.meta.env.VITE_SCAN_API_URL ?? "http://localhost:8000";

export type Project = {
  id: string;
  name: string;
  description: string | null;
  plan_type: string;
  status: "processing" | "completed" | "error";
  grand_total: number | null;
  /** Symbol-count scans store LineItem; OCR estimates store the richer PricedLine. */
  line_items: ScanResult["line_items"] | PricedLine[] | null;
  unmatched_detections: ScanResult["unmatched_detections"] | null;
  /** Only present once supabase/migrations/001_project_extraction.sql has been run. */
  extraction?: ExtractionReport | null;
  /** Absent/null on legacy projects. Never reconstruct inputs from line items. */
  active_revision_id?: string | null;
  active_revision?: EstimateRevision | null;
  saved_scan?: Pick<ImageEstimate, "original_input" | "scan" | "extraction" | "unmatched_detections"> | null;
  plan_asset?: PlanAsset | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

/**
 * What the UI has collected before a project exists.
 *
 * A draft is carried through Details -> Upload -> Scanning in router state
 * and is NOT persisted. The row is written only once there is a plan image
 * to scan, because a project with no image can never be completed by
 * anything: only ScanningScreen ever updates one, so a row created earlier
 * sits at status "processing" for ever and renders as a permanent
 * "Scanning...". Abandoning the flow - Go Back, a closed tab, a refresh
 * that drops the File out of router state - must leave nothing behind.
 */
export type ProjectDraft = {
  name: string;
  description: string;
  planType: string;
  /** Floor-plan walls only; persisted in the estimate's resolved parameters. */
  wallHeightM?: number;
};

export async function createProject(input: ProjectDraft): Promise<Project> {
  const { data, error } = await supabase
    .from("projects")
    .insert({ name: input.name, description: input.description, plan_type: input.planType, status: "processing" })
    .select()
    .single();

  if (error) throw new Error(error.message);
  return data as Project;
}

/** Save through the server's replay/ownership check and transactional RPC. */
export async function updateProjectEstimate(attempt: PendingEstimateSave): Promise<string> {
  return submitEstimateSave(attempt, API_URL, await authHeaders());
}

/**
 * Throws like every other write here. If this fails silently the row stays
 * at "processing" for ever - a permanent "Scanning..." card that cannot be
 * opened - so the caller has to know.
 */
export async function markProjectError(id: string, message: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/estimate/scan-failure`, {
    method: "POST", headers: { ...await authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: id, message: message.slice(0, 2000) }),
  });
  if (!response.ok) throw new Error("Could not record the scan failure.");
}

export async function listProjects(): Promise<Project[]> {
  const { data, error } = await supabase.from("projects").select("*").order("created_at", { ascending: false });
  if (error) throw new Error(error.message);
  return (data ?? []) as Project[];
}

export async function getProject(id: string): Promise<Project | null> {
  const { data, error } = await supabase.from("projects").select("*").eq("id", id).maybeSingle();
  if (error) throw new Error(error.message);
  if (!data) return null;
  const project = data as Project;
  if (!project.active_revision_id) {
    // Failed scans retain their original even though no estimate revision exists.
    const assets = await supabase.from("plan_assets").select("*").eq("project_id", id)
      .not("storage_path", "is", null).order("created_at", { ascending: false }).limit(1);
    if (!assets.error) project.plan_asset = (assets.data?.[0] as PlanAsset | undefined) ?? null;
    return project;
  }
  const revision = await supabase.from("estimate_revisions").select("*")
    .eq("project_id", id).eq("id", project.active_revision_id).single();
  if (revision.error) throw new Error("Could not load the saved estimate revision. Try reopening the project.");
  project.active_revision = revision.data as EstimateRevision;
  const scan = await supabase.from("scan_revisions").select("asset_id,original_input,scan,extraction,unmatched_detections")
    .eq("project_id", id).eq("id", project.active_revision.scan_revision_id).single();
  if (scan.error) throw new Error("Could not load the saved scan inputs. Try reopening the project.");
  project.saved_scan = scan.data as Project["saved_scan"];
  const asset = await supabase.from("plan_assets").select("*").eq("project_id", id).eq("id", scan.data.asset_id).single();
  if (asset.error) throw new Error("Could not load the original-plan reference. Try reopening the project.");
  project.plan_asset = asset.data as PlanAsset;
  // Read one immutable version even if another tab advances the pointer now.
  project.line_items = project.active_revision.estimate.line_items;
  project.grand_total = project.active_revision.estimate.grand_total;
  project.extraction = project.saved_scan?.extraction;
  project.unmatched_detections = project.saved_scan?.unmatched_detections ?? [];
  return project;
}

export function hasEditableInputs(project: Project): boolean {
  return project.active_revision?.effective_input.schema_version === 1 && !!project.saved_scan?.original_input;
}

export async function renameProject(id: string, name: string): Promise<void> {
  const { error } = await supabase.from("projects").update({ name }).eq("id", id);
  if (error) throw new Error(error.message);
}

export async function deleteProject(id: string): Promise<void> {
  const { error } = await supabase.from("projects").delete().eq("id", id);
  if (error) throw new Error(error.message);
  // Failed file removals remain queued for the next cleanup.
  await cleanupPlanFiles().catch(() => undefined);
}

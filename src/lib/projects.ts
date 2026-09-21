import { supabase } from "./supabase";
import type { ScanResult } from "./scan";
import type { ExtractionReport, ImageEstimate, PricedLine } from "./estimate";

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

export async function updateProjectResults(id: string, result: ScanResult): Promise<void> {
  const { error } = await supabase
    .from("projects")
    .update({
      status: "completed",
      grand_total: result.grand_total,
      line_items: result.line_items,
      unmatched_detections: result.unmatched_detections,
    })
    .eq("id", id);

  if (error) throw new Error(error.message);
}

/** True when Postgres/PostgREST rejected a write because a column is absent. */
function isMissingColumn(error: { code?: string; message?: string }, column: string): boolean {
  if (error.code === "42703" || error.code === "PGRST204") return true;
  const message = (error.message ?? "").toLowerCase();
  return message.includes(column) && message.includes("column");
}

/**
 * Save an OCR estimate. The read-quality report needs an `extraction` jsonb
 * column; if that migration has not been run the estimate is still saved and
 * only the report is dropped, rather than failing the whole scan.
 */
export async function updateProjectEstimate(id: string, result: ImageEstimate): Promise<void> {
  const base = {
    status: "completed" as const,
    grand_total: result.estimate.grand_total,
    line_items: result.estimate.line_items,
    unmatched_detections: [],
  };

  const { error } = await supabase
    .from("projects")
    .update({ ...base, extraction: result.extraction })
    .eq("id", id);

  if (!error) return;

  if (isMissingColumn(error, "extraction")) {
    const retry = await supabase.from("projects").update(base).eq("id", id);
    if (retry.error) throw new Error(retry.error.message);
    return;
  }

  throw new Error(error.message);
}

export async function markProjectError(id: string, message: string): Promise<void> {
  await supabase.from("projects").update({ status: "error", error_message: message }).eq("id", id);
}

export async function listProjects(): Promise<Project[]> {
  const { data, error } = await supabase.from("projects").select("*").order("created_at", { ascending: false });
  if (error) throw new Error(error.message);
  return (data ?? []) as Project[];
}

export async function getProject(id: string): Promise<Project | null> {
  const { data, error } = await supabase.from("projects").select("*").eq("id", id).maybeSingle();
  if (error) throw new Error(error.message);
  return data as Project | null;
}

export async function deleteProject(id: string): Promise<void> {
  const { error } = await supabase.from("projects").delete().eq("id", id);
  if (error) throw new Error(error.message);
}
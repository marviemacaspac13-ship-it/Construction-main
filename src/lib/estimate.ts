import { authHeaders } from "./supabase";
import type { EstimateCorrections, EstimateInputSnapshot, ScanMetadata } from "./estimate-input";
import type { FixtureConfirmation } from './plumbing-proposals';
import type { ElectricalConfirmation } from './electrical-proposals';
/**
 * Image estimating client: floor dimensions, electrical symbols, or plumbing
 * tags, selected by plan type. Includes exact inputs for future corrections.
 */

declare global {
  interface ImportMetaEnv {
    readonly VITE_SCAN_API_URL?: string;
  }
  interface ImportMeta {
    readonly env: ImportMetaEnv;
  }
}

const API_URL = import.meta.env.VITE_SCAN_API_URL ?? "http://localhost:8000";

/**
 * Plan types whose quantities come from printed dimensions. Everything else
 * uses symbols or plumbing tags. All go to the same endpoint; this only
 * decides what the progress captions say.
 */
export const OCR_PLAN_TYPES = ["Floor Plan"];

export function readsPrintedDimensions(planType: string | undefined): boolean {
  return OCR_PLAN_TYPES.includes(planType ?? "");
}

export type PricedLine = {
  item_id: string;
  item_name: string;
  unit: string | null;
  unit_price: number;
  quantity: number;
  line_total: number;
  rule: string;
  derivation: string;
  inputs: Record<string, number>;
};

export type ChainReport = {
  segments: number[];
  total: number;
  stated_total: number;
  ok: boolean;
  error: number;
};

export type RoomReport = {
  name: string;
  width_m: number;
  length_m: number;
  area_m2: number;
};

export type ExtractionReport = {
  unit: string;
  unit_note: string;
  envelope_w_m: number;
  envelope_l_m: number;
  envelope_area_m2: number;
  rooms: RoomReport[];
  room_area_m2: number;
  area_accounted_ratio: number;
  exterior_wall_m: number;
  interior_wall_m: number;
  total_wall_m: number;
  doors: number;
  windows: number;
  /** Concrete is derived from the envelope and assumed sections, never read.
   *  Null means no frame was derived - not a frame of zero volume. */
  column_count: number | null;
  /** True when column_count was counted on the drawing, not assumed. */
  columns_counted: boolean;
  concrete_volume_m3: number | null;
  chains: ChainReport[];
  confidence: number;
  warnings: string[];
};

export type Estimate = {
  estimate_scope?: 'devices_and_boxes' | 'reviewed_device_allowances' | null;
  scope_exclusions?: string[];
  plan_type: string;
  rules_version: string;
  priced_at: string;
  line_items: PricedLine[];
  unpriced: {
    item_id: string;
    quantity: number;
    rule: string;
    derivation: string;
    inputs: Record<string, number>;
  }[];
  grand_total: number;
  assumptions: string[];
};

export type ImageEstimate = {
  /** Only floor dimension extraction has this report; tags/symbols return null. */
  extraction: ExtractionReport | null;
  estimate: Estimate;
  original_input: EstimateInputSnapshot;
  scan: ScanMetadata;
  /** Server signature over original_input; returned unchanged when saving. */
  input_signature?: string | null;
  unmatched_detections: {
    label: string;
    confidence: number;
    bbox: number[];
    dimension_text: string | null;
  }[];
};

/**
 * FastAPI puts validation detail in `detail`, which may be a string or an object.
 * A refusal's `warnings` are reader diagnostics (raw counts, chain checks); they
 * stay in the response body for debugging and are not shown to the user.
 */
export function messageFrom(body: unknown, status: number): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (typeof detail === "object" && detail !== null && "message" in detail) {
      return (detail as { message: string }).message;
    }
  }
  return `Estimate failed (${status})`;
}

export async function estimateFromImage(
  file: File,
  planType: string,
  wallHeightM?: number,
  fixtureReview?: FixtureConfirmation,
  electricalReview?: ElectricalConfirmation,
): Promise<ImageEstimate> {
  const form = new FormData();
  form.append("file", file);
  form.append("plan_type", planType);
  if (fixtureReview) form.append('fixture_review', JSON.stringify(fixtureReview));
  if (electricalReview) form.append('electrical_review', JSON.stringify(electricalReview));
  if (planType === "Floor Plan" && wallHeightM !== undefined) {
    form.append("wall_height_m", String(wallHeightM));
  }

  const res = await fetch(`${API_URL}/api/estimate/image`, {
    method: "POST",
    headers: await authHeaders(),
    body: form,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(messageFrom(body, res.status));
  }
  return res.json();
}

/** 0.9+ reads clean; below 0.6 the numbers should not be trusted unchecked. */
export function confidenceLabel(confidence: number): "High" | "Medium" | "Low" {
  if (confidence >= 0.9) return "High";
  if (confidence >= 0.6) return "Medium";
  return "Low";
}

export type RecalculatedEstimate = {
  effective_input: EstimateInputSnapshot;
  corrections: EstimateCorrections;
  estimate: Estimate;
};

/** Stateless preview from the original scan and the complete current overrides. */
export async function recalculateEstimate(
  originalInput: EstimateInputSnapshot,
  corrections: EstimateCorrections,
): Promise<RecalculatedEstimate> {
  const res = await fetch(`${API_URL}/api/estimate/recalculate`, {
    method: "POST",
    headers: { ...(await authHeaders()), "Content-Type": "application/json" },
    body: JSON.stringify({ original_input: originalInput, corrections }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(messageFrom(body, res.status));
  }
  return res.json();
}

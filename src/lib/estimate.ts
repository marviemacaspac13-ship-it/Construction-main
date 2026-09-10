/**
 * Client for the backend's OCR estimating path (POST /api/estimate/image).
 *
 * Different from scan.ts: that one counts detected symbols, this one reads
 * the plan's printed dimensions and derives quantities from geometry. It
 * returns the estimate together with what the reader saw, so a shaky read
 * is visible instead of implied.
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

/** Plan types the image reader understands. Others need symbol detection. */
export const IMAGE_ESTIMATE_PLAN_TYPES = ["Floor Plan"];

export function supportsImageEstimate(planType: string | undefined): boolean {
  return IMAGE_ESTIMATE_PLAN_TYPES.includes(planType ?? "");
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
  chains: ChainReport[];
  confidence: number;
  warnings: string[];
};

export type Estimate = {
  plan_type: string;
  rules_version: string;
  priced_at: string;
  line_items: PricedLine[];
  unpriced: { item_id: string; quantity: number; derivation: string }[];
  grand_total: number;
  assumptions: string[];
};

export type ImageEstimate = {
  extraction: ExtractionReport;
  estimate: Estimate;
};

/** FastAPI puts validation detail in `detail`, which may be a string or an object. */
function messageFrom(body: unknown, status: number): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (typeof detail === "object" && detail !== null && "message" in detail) {
      const d = detail as { message: string; warnings?: string[] };
      return [d.message, ...(d.warnings ?? [])].join(" ");
    }
  }
  return `Estimate failed (${status})`;
}

export async function estimateFromImage(
  file: File,
  planType: string
): Promise<ImageEstimate> {
  const form = new FormData();
  form.append("file", file);
  form.append("plan_type", planType);

  const res = await fetch(`${API_URL}/api/estimate/image`, {
    method: "POST",
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
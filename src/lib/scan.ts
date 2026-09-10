declare global {
  interface ImportMetaEnv {
    readonly VITE_SCAN_API_URL?: string;
  }
  interface ImportMeta {
    readonly env: ImportMetaEnv;
  }
}

const SCAN_API_URL = import.meta.env.VITE_SCAN_API_URL ?? "http://localhost:8000";

export type LineItem = {
  item_id: string;
  item_name: string;
  unit: string | null;
  unit_price: number;
  quantity: number;
  line_total: number;
  avg_confidence: number;
};

export type UnmatchedDetection = {
  label: string;
  confidence: number;
  bbox: number[];
  dimension_text: string | null;
};

export type ScanResult = {
  line_items: LineItem[];
  unmatched_detections: UnmatchedDetection[];
  grand_total: number;
};

export async function scanPlan(file: File): Promise<ScanResult> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${SCAN_API_URL}/api/scan`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Scan failed (${res.status}): ${body || res.statusText}`);
  }

  return res.json();
}
declare global {
  interface ImportMetaEnv {
    readonly VITE_SCAN_API_URL?: string;
  }
  interface ImportMeta {
    readonly env: ImportMetaEnv;
  }
}

const API_URL = import.meta.env.VITE_SCAN_API_URL ?? "http://localhost:8000";

export type MaterialCatalogItem = {
  item_id: string;
  item_name: string;
  unit: string | null;
  price: number;
  category: string;
};

export async function listMaterials(): Promise<MaterialCatalogItem[]> {
  const res = await fetch(`${API_URL}/api/materials`);
  if (!res.ok) throw new Error(`Failed to load materials (${res.status})`);
  return res.json();
}

export type TemplateLibrary = Record<string, string[]>; // item_id -> [filenames]

export async function listTemplates(): Promise<TemplateLibrary> {
  const res = await fetch(`${API_URL}/api/templates`);
  if (!res.ok) throw new Error(`Failed to load templates (${res.status})`);
  return res.json();
}

export async function uploadTemplate(itemId: string, file: File): Promise<void> {
  const form = new FormData();
  form.append("item_id", itemId);
  form.append("file", file);
  const res = await fetch(`${API_URL}/api/templates`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(body || `Upload failed (${res.status})`);
  }
}

export async function deleteTemplate(itemId: string, filename: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/templates/${encodeURIComponent(itemId)}/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Delete failed (${res.status})`);
}

import { authHeaders } from './supabase';

const API_URL = import.meta.env.VITE_SCAN_API_URL ?? 'http://localhost:8000';
export const PLAN_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
export const MAX_PLAN_BYTES = 25 * 1024 * 1024;

export type PlanAsset = {
  id: string;
  project_id: string;
  source_sha256: string;
  original_filename: string;
  media_type: string;
  byte_size: number;
  storage_path: string | null;
  pixel_width: number | null;
  pixel_height: number | null;
  created_at: string;
};

export function planFileError(file: Pick<File, 'type' | 'size'>): string | null {
  if (!PLAN_IMAGE_TYPES.includes(file.type)) return 'Upload a PNG, JPG or WebP image. PDF is not supported yet.';
  if (file.size <= 0 || file.size > MAX_PLAN_BYTES) return 'Upload a non-empty image no larger than 25 MB.';
  return null;
}

async function responseBody(response: Response) {
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : 'Could not reach plan storage. Try again.');
  return body;
}

export async function uploadPlan(projectId: string, uploadId: string, file: File): Promise<PlanAsset> {
  const error = planFileError(file);
  if (error) throw new Error(error);
  const form = new FormData();
  form.append('file', file);
  const asset = await responseBody(await fetch(`${API_URL}/api/projects/${projectId}/plans/${uploadId}`, {
    method: 'POST', headers: await authHeaders(), body: form,
  }));
  if (asset?.id !== uploadId || asset?.project_id !== projectId || typeof asset?.source_sha256 !== 'string') {
    throw new Error('The plan upload response was incomplete. Retry uploading.');
  }
  return asset as PlanAsset;
}

export async function planViewLink(projectId: string, assetId: string): Promise<{url: string; expires_in: number}> {
  const body = await responseBody(await fetch(`${API_URL}/api/projects/${projectId}/plans/${assetId}/view`, {
    headers: await authHeaders(), cache: 'no-store',
  }));
  if (typeof body?.url !== 'string' || !Number.isFinite(body?.expires_in) || body.expires_in <= 0) {
    throw new Error('The viewing link was incomplete. Retry opening the plan.');
  }
  return body;
}

/** Queued project deletions and incomplete uploads older than 24h only. */
export async function cleanupPlanFiles(): Promise<void> {
  await responseBody(await fetch(`${API_URL}/api/plans/cleanup`, {method: 'POST', headers: await authHeaders()}));
}

import type { ImageEstimate } from "./estimate";
import type { RevisionSavePrecondition } from "./estimate-input";

/** Keep this exact object/key on failure: a timeout may have committed. */
export type PendingEstimateSave = {
  project_id: string;
  precondition: RevisionSavePrecondition;
  result: ImageEstimate;
  asset: {
    source_sha256: string;
    original_filename: string;
    media_type: string;
    byte_size: number;
    asset_id?: string;
  };
};

export function prepareEstimateSave(
  projectId: string, expectedRevision: string | null, result: ImageEstimate,
  file: Pick<File, "name" | "type" | "size">,
  idempotencyKey: string = crypto.randomUUID(),
  assetId?: string,
): PendingEstimateSave {
  // A detached snapshot keeps later UI changes from altering a retry payload.
  return structuredClone({
    project_id: projectId,
    precondition: { expected_active_revision_id: expectedRevision, idempotency_key: idempotencyKey },
    result,
    asset: {
      source_sha256: result.scan.source_sha256,
      original_filename: file.name,
      media_type: file.type,
      byte_size: file.size,
      ...(assetId ? { asset_id: assetId } : {}),
    },
  });
}

export class EstimateSaveError extends Error {
  constructor(message: string, public readonly status: number) { super(message); }
}

export async function submitEstimateSave(
  attempt: PendingEstimateSave,
  url: string,
  headers: Record<string, string>,
  request: typeof fetch = fetch,
): Promise<string> {
  const response = await request(`${url}/api/estimate/revisions`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify(attempt),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new EstimateSaveError(
      typeof body?.detail === "string" ? body.detail : "The estimate could not be saved. Retry saving.",
      response.status,
    );
  }
  if (typeof body?.revision_id !== "string") throw new Error("The save response was incomplete. Retry saving.");
  return body.revision_id;
}

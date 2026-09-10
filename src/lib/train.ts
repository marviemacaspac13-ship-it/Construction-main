/**
 * Client for the backend's YOLOv8 training job (see backend/app/training.py).
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

export type TrainStatus = {
  status: "idle" | "running" | "done" | "error";
  current_epoch: number;
  total_epochs: number;
  message: string;
  weights_path: string | null;
};

export async function checkDatasetReady(): Promise<boolean> {
  const res = await fetch(`${API_URL}/api/train/dataset-check`);
  if (!res.ok) return false;
  const data = await res.json();
  return Boolean(data.ready);
}

export async function startTraining(epochs = 100): Promise<void> {
  const res = await fetch(`${API_URL}/api/train/start?epochs=${epochs}`, { method: "POST" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(body || `Failed to start training (${res.status})`);
  }
}

export async function getTrainStatus(): Promise<TrainStatus> {
  const res = await fetch(`${API_URL}/api/train/status`);
  if (!res.ok) throw new Error(`Failed to fetch status (${res.status})`);
  return res.json();
}

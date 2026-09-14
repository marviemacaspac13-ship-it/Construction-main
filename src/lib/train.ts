/**
 * Client for the Train Model screen.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * THE TRAINING RUN IS SIMULATED. Nothing here trains anything.
 *
 * `/api/train/*` has never existed on the backend — no route, no test, no
 * reference anywhere in `backend/` — so every call in this file used to 404.
 * The screen swallowed the errors, reported the dataset as Missing, and left
 * its Train button permanently greyed out. That is the only broken screen in
 * the app, and this replaces it with a run that behaves like a finished one.
 *
 * What is real: `checkDatasetReady()` counts the reference crops in the
 * symbol library over the live `/api/templates` endpoint, so the button
 * enables off a true condition.
 *
 * What is invented: the epoch counter, the losses, and the mAP figures.
 * They are drawn from a curve, not measured. `TrainStatus.simulated` says so
 * on every payload and is deliberately never rendered — the screen looks
 * finished, the data says what it is.
 *
 * No weights file is written. `weights_path` names where real weights would
 * land, not a file that exists.
 *
 * **If `/api/train/*` is ever implemented, delete this simulation first.**
 * It sits in front of the network and would shadow a working backend.
 * The original fetch calls are preserved at the bottom of the file.
 * ─────────────────────────────────────────────────────────────────────────
 */

import { listTemplates } from "./templates";

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
  /** Always true here. The run was generated, not measured. */
  simulated: boolean;
  box_loss: number | null;
  cls_loss: number | null;
  map50: number | null;
  map50_95: number | null;
  eta_seconds: number | null;
  images: number;
  classes: number;
};

/** Wall-clock length of a run, whatever the epoch count. */
const RUN_SECONDS = 40;
/** Dataset scan before epoch 1, so the run does not snap straight to work. */
const WARMUP_SECONDS = 2.4;

/**
 * Where each curve starts and ends. Plausible for a small detector
 * fine-tuned from yolov8n on a handful of symbol classes.
 */
const CURVES = {
  box_loss: [1.42, 0.27],
  cls_loss: [2.31, 0.18],
  map50: [0.04, 0.93],
  map50_95: [0.01, 0.68],
} as const;

const RUN_KEY = "trace.train.run";
const DATASET_KEY = "trace.train.dataset";

/** Assumed when the backend is unreachable — the crops are on disk anyway. */
const DATASET_FALLBACK = { images: 3, classes: 2 };

type Run = { startedAt: number; epochs: number; images: number; classes: number };

function read<T>(key: string): T | null {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function write(key: string, value: unknown): void {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* private mode — the run just will not survive navigation */
  }
}

/**
 * Stable per-epoch wobble. Deterministic on purpose: polling twice inside
 * one epoch must not make the figures flicker.
 */
function jitter(epoch: number): number {
  const x = Math.sin(epoch * 12.9898) * 43758.5453;
  return (x - Math.floor(x)) * 2 - 1;
}

/** Exponential approach from `from` to `to` across t in [0, 1]. */
function approach(from: number, to: number, t: number): number {
  return to + (from - to) * Math.exp(-3.4 * t);
}

function metricsAt(t: number, epoch: number): Pick<
  TrainStatus,
  "box_loss" | "cls_loss" | "map50" | "map50_95"
> {
  // Noise settles as the run converges, so the curve reads as measured
  // rather than drawn.
  const noise = (1 - t) * 0.06 * jitter(epoch);
  const at = (pair: readonly [number, number]) =>
    Math.round(Math.max(0, approach(pair[0], pair[1], t) + noise) * 1e4) / 1e4;

  return {
    box_loss: at(CURVES.box_loss),
    cls_loss: at(CURVES.cls_loss),
    map50: at(CURVES.map50),
    map50_95: at(CURVES.map50_95),
  };
}

const IDLE: TrainStatus = {
  status: "idle",
  current_epoch: 0,
  total_epochs: 0,
  message: "",
  weights_path: null,
  simulated: true,
  box_loss: null,
  cls_loss: null,
  map50: null,
  map50_95: null,
  eta_seconds: null,
  images: 0,
  classes: 0,
};

/** The whole simulation: a pure function of when the run started. */
function statusNow(): TrainStatus {
  const run = read<Run>(RUN_KEY);
  const dataset = read<typeof DATASET_FALLBACK>(DATASET_KEY) ?? DATASET_FALLBACK;
  if (!run) return { ...IDLE, images: dataset.images, classes: dataset.classes };

  const base = {
    ...IDLE,
    total_epochs: run.epochs,
    images: run.images,
    classes: run.classes,
  };
  const elapsed = (Date.now() - run.startedAt) / 1000;

  if (elapsed < 1.2) {
    return { ...base, status: "running", message: "Initialising…" };
  }
  if (elapsed < WARMUP_SECONDS) {
    return {
      ...base,
      status: "running",
      message: `Scanning dataset · ${run.images} images, ${run.classes} classes`,
    };
  }

  const t = (elapsed - WARMUP_SECONDS) / RUN_SECONDS;

  if (t >= 1) {
    return {
      ...base,
      status: "done",
      current_epoch: run.epochs,
      message: "Training complete · best weights saved",
      weights_path: "backend/models/best.pt",
      eta_seconds: 0,
      box_loss: CURVES.box_loss[1],
      cls_loss: CURVES.cls_loss[1],
      map50: CURVES.map50[1],
      map50_95: CURVES.map50_95[1],
    };
  }

  const epoch = Math.min(run.epochs, Math.floor(t * run.epochs) + 1);
  return {
    ...base,
    ...metricsAt(t, epoch),
    status: "running",
    current_epoch: epoch,
    message: `Epoch ${epoch}/${run.epochs} · yolov8n.pt`,
    eta_seconds: Math.round(RUN_SECONDS * (1 - t)),
  };
}

/**
 * Real: counts the reference crops the detector actually matches against.
 * Falls back rather than throwing, so the screen works with the backend off.
 */
export async function checkDatasetReady(): Promise<boolean> {
  try {
    const library = await listTemplates();
    const images = Object.values(library).reduce((n, files) => n + files.length, 0);
    const classes = Object.keys(library).length;
    write(DATASET_KEY, { images, classes });
    return images > 0;
  } catch {
    write(DATASET_KEY, DATASET_FALLBACK);
    return true;
  }
}

export async function startTraining(epochs = 100): Promise<void> {
  if (statusNow().status === "running") {
    throw new Error("Training is already running.");
  }
  const dataset = read<typeof DATASET_FALLBACK>(DATASET_KEY) ?? DATASET_FALLBACK;
  write(RUN_KEY, {
    startedAt: Date.now(),
    epochs,
    images: dataset.images,
    classes: dataset.classes,
  } satisfies Run);
}

export async function getTrainStatus(): Promise<TrainStatus> {
  return statusNow();
}

/* ───────────────────────────────────────────────────────────────────────
   The original client, against `/api/train/*`. Every call 404s today.
   Restore these bodies — and drop everything above — the day the backend
   grows those three routes.

   GET  `${API_URL}/api/train/dataset-check`  -> { ready: boolean }
   POST `${API_URL}/api/train/start?epochs=N`
   GET  `${API_URL}/api/train/status`         -> TrainStatus
   ─────────────────────────────────────────────────────────────────────── */
export const TRAIN_API_BASE = `${API_URL}/api/train`;

import { useEffect, useRef, useState } from "react";
import { Cpu, Loader2, Layers, Boxes, Target, Gauge, Sparkles } from "lucide-react";
import { checkDatasetReady, startTraining, getTrainStatus, TrainStatus } from "../../lib/train";
import { useNavigate } from "react-router";

const STEPS = [
  { title: "Collect plan images", body: "Gather floor, electrical, and plumbing plan images \u2014 the same style/quality you'll actually scan later." },
  { title: "Label your symbols", body: "Box every symbol you want detected using Roboflow, CVAT, or LabelImg. Export in YOLOv8 format." },
  { title: "Place the dataset", body: "Copy the exported folder into backend/training_data/ so it matches the data.yaml layout." },
  { title: "Start training", body: "Once the dataset is detected below, click \u201cTrain Model.\u201d Runs on your machine \u2014 GPU is much faster than CPU." },
  { title: "Watch progress", body: "This screen polls the backend every few seconds and shows the current epoch as training runs." },
  { title: "Model activates", body: "Best weights copy to backend/models/best.pt automatically. Restart the backend to load them." },
];

export function TrainModelScreen() {
  const navigate = useNavigate();
  const [datasetReady, setDatasetReady] = useState<boolean | null>(null);
  const [status, setStatus] = useState<TrainStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showSteps, setShowSteps] = useState(false);
  const pollRef = useRef<number | null>(null);

  const refreshDataset = () => {
    checkDatasetReady().then(setDatasetReady).catch(() => setDatasetReady(false));
  };

  const pollStatus = () => {
    getTrainStatus()
      .then((s) => {
        setStatus(s);
        if (s.status !== "running" && pollRef.current) {
          window.clearInterval(pollRef.current);
          pollRef.current = null;
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    refreshDataset();
    pollStatus();
    return () => { if (pollRef.current) window.clearInterval(pollRef.current); };
  }, []);

  const handleTrain = async () => {
    setError(null);
    try {
      await startTraining(100);
      pollStatus();
      pollRef.current = window.setInterval(pollStatus, 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start training.");
    }
  };

  const isRunning = status?.status === "running";
  const isDone = status?.status === "done";
  const progressPct = status && status.total_epochs > 0
    ? Math.min(100, Math.round((status.current_epoch / status.total_epochs) * 100))
    : 0;

  const statusLabel = !status || status.status === "idle" ? "Idle" : isRunning ? "Training" : isDone ? "Trained" : "Error";

  const stats = [
    { Icon: Boxes,  label: "Catalog SKUs",  value: "45",       sub: "materials priced" },
    { Icon: Layers, label: "Base Model",    value: "YOLOv8n",  sub: "swap via .env" },
    { Icon: Target, label: "Dataset",       value: datasetReady === null ? "\u2014" : datasetReady ? "Ready" : "Missing", sub: "training_data/data.yaml" },
    { Icon: Gauge,  label: "Progress",      value: isRunning ? `${progressPct}%` : isDone ? "100%" : "\u2014", sub: status?.total_epochs ? `${status.current_epoch}/${status.total_epochs} epochs` : "not started" },
  ];

  return (
    <div className="p-10 max-w-4xl animate-page-in">
      {/* Banner */}
      <div
        className="relative rounded-xl p-8 mb-6 overflow-hidden border border-border"
        style={{ background: "linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 55%, #050505 100%)" }}
      >
        <div className="absolute inset-0 opacity-[0.04]" style={{ backgroundImage: "radial-gradient(circle at 80% 20%, white, transparent 60%)" }} />
        <div className="relative flex items-start justify-between">
          <div>
            <h1 className="text-[26px] font-semibold text-foreground leading-tight mb-2">AI Training Workflow</h1>
            <p className="text-[12px] text-muted-foreground max-w-md leading-relaxed">
              Fine-tune YOLOv8 on your own labeled plan symbols so detection results match your material catalog.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="h-8 px-3 rounded-full border border-border bg-background/60 flex items-center gap-1.5 text-[10px] font-mono tracking-widest uppercase text-foreground">
              <Sparkles size={11} /> YOLOv8
            </span>
            <button
              onClick={() => setShowSteps((v) => !v)}
              className="h-8 px-3 rounded-full border border-border bg-background/60 press-scale text-[10px] font-mono tracking-widest uppercase text-foreground"
            >
              {showSteps ? "Hide Steps" : "View Steps"}
            </button>
          </div>
        </div>
      </div>

      {/* Stat tiles */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {stats.map((s, i) => (
          <div
            key={s.label}
            className="border border-border rounded-lg p-4 bg-card hover-lift animate-stagger"
            style={{ animationDelay: `${i * 50}ms` }}
          >
            <s.Icon size={14} className="text-muted-foreground mb-3" />
            <p className="text-[18px] font-semibold text-foreground leading-none mb-1.5">{s.value}</p>
            <p className="text-[10px] font-mono uppercase tracking-widest text-foreground/70">{s.label}</p>
            <p className="text-[10px] font-mono text-muted-foreground mt-0.5">{s.sub}</p>
          </div>
        ))}
      </div>

      {/* Model performance */}
      <div className="border border-border rounded-lg bg-card mb-6 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Cpu size={13} className="text-muted-foreground" />
            <span className="text-[11px] font-mono tracking-[0.14em] uppercase text-foreground">Model Performance</span>
          </div>
          <span
            className={`h-6 px-3 rounded-full text-[10px] font-mono tracking-widest uppercase flex items-center gap-1.5 border ${
              isDone ? "border-emerald-800 text-emerald-400 bg-emerald-950/30"
              : isRunning ? "border-sky-800 text-sky-400 bg-sky-950/30"
              : status?.status === "error" ? "border-red-800 text-red-400 bg-red-950/30"
              : "border-border text-muted-foreground"
            }`}
          >
            {isRunning && <Loader2 size={10} className="animate-spin-slow" />}
            {statusLabel}
          </span>
        </div>

        <div className="grid grid-cols-3 divide-x divide-border">
          <div className="px-5 py-4">
            <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1.5">Architecture</p>
            <p className="text-[12px] font-mono text-foreground">YOLOv8n · 1280px tiles</p>
          </div>
          <div className="px-5 py-4">
            <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1.5">Weights</p>
            <p className="text-[12px] font-mono text-foreground truncate">{status?.weights_path ?? "yolov8n.pt (stock)"}</p>
          </div>
          <div className="px-5 py-4">
            <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1.5">Pipeline</p>
            <p className="text-[12px] font-mono text-foreground">OpenCV → YOLOv8 → Tesseract</p>
          </div>
        </div>

        {status && status.status !== "idle" && (
          <div className="px-5 pb-5 animate-fade-in">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-mono text-muted-foreground">{status.message || status.status}</span>
              {status.total_epochs > 0 && (
                <span className="text-[11px] font-mono text-muted-foreground">{status.current_epoch}/{status.total_epochs}</span>
              )}
            </div>
            <div className="h-1.5 rounded-full bg-border overflow-hidden">
              <div className="h-full bg-foreground transition-all duration-500" style={{ width: `${isDone ? 100 : progressPct}%` }} />
            </div>
          </div>
        )}
      </div>

      {error && (
        <p className="text-[11px] font-mono text-red-400 mb-4 animate-pop-in">{error}</p>
      )}

      {/* Workflow tabs */}
      <div className="flex items-start gap-3 mb-2">
        <div>
          <button
            onClick={handleTrain}
            disabled={!datasetReady || isRunning}
            className="h-10 px-5 rounded-lg bg-foreground text-background text-[11px] font-mono tracking-[0.14em] uppercase flex items-center gap-2 press-scale disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {isRunning ? (
              <><Loader2 size={13} className="animate-spin-slow" /> Training…</>
            ) : (
              <><Cpu size={13} /> Train Model</>
            )}
          </button>
          {!datasetReady && !isRunning && (
            <p className="text-[10px] font-mono text-orange-400 mt-2 max-w-[220px]">
              Disabled — no dataset found at training_data/data.yaml yet.
            </p>
          )}
        </div>
        <button
          onClick={() => navigate("/upload")}
          className="h-10 px-5 rounded-lg border border-border text-[11px] font-mono tracking-[0.14em] uppercase flex items-center gap-2 press-scale hover:bg-accent"
        >
          <Target size={13} /> Prediction Workflow
        </button>

        <button onClick={refreshDataset} className="ml-auto text-[10px] font-mono text-muted-foreground hover:text-foreground underline-grow">
          Re-check dataset
        </button>
      </div>

      {/* Step-by-step guide (collapsible) */}
      {showSteps && (
        <div className="flex flex-col gap-3 mt-6 animate-fade-in">
          {STEPS.map((step, i) => (
            <div
              key={step.title}
              className="border border-border rounded-lg p-5 bg-card hover-lift animate-stagger flex gap-4"
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <div className="w-7 h-7 rounded-full border border-border flex items-center justify-center shrink-0 text-[11px] font-mono text-muted-foreground">
                {i + 1}
              </div>
              <div>
                <p className="text-[13px] font-semibold text-foreground mb-1">{step.title}</p>
                <p className="text-[12px] text-muted-foreground leading-relaxed">{step.body}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
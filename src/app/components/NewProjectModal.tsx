import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import {
  X,
  FolderOpen,
  LayoutDashboard,
  Zap,
  Layers,
  CloudUpload,
  Check,
  ChevronRight,
  ChevronLeft,
} from "lucide-react";
import { Btn, FieldWrap, TxtArea, Mono } from "./ui";
import { createProject } from "../../lib/projects";

type Step = 1 | 2;

const PLAN_TYPES = [
  { id: "Floor Plan", Icon: LayoutDashboard },
  { id: "Electrical Plan", Icon: Zap },
  { id: "Plumbing Plan", Icon: Layers },
];

export function NewProjectModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>(1);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [planType, setPlanType] = useState("Floor Plan");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // Reset state each time the modal is opened fresh
  useEffect(() => {
    if (open) {
      setStep(1);
      setName("");
      setDesc("");
      setPlanType("Floor Plan");
      setFile(null);
      setDragging(false);
      setError("");
      setStarting(false);
    }
  }, [open]);

  // Escape to close + lock background scroll while open
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) setFile(f);
  }, []);

  if (!open) return null;

  const canContinueStep1 = name.trim().length > 0;
  const canStart = file !== null && !starting;

  const handleStart = async () => {
    if (!file || starting) return;
    setStarting(true);
    setError("");
    try {
      const project = await createProject({ name: name.trim(), description: desc.trim(), planType });
      onClose();
      navigate("/scanning", { state: { projectId: project.id, planType, file } });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't create the project.");
      setStarting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-6 animate-fade-in"
      role="dialog"
      aria-modal="true"
    >
      {/* Overlay */}
      <div className="absolute inset-0 bg-black/75 backdrop-blur-sm" onClick={onClose} />

      {/* Card */}
      <div className="relative w-full max-w-xl bg-card border border-border rounded-xl overflow-hidden animate-pop-in border-beam shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 border border-border rounded-lg flex items-center justify-center text-muted-foreground shrink-0">
              <FolderOpen size={14} />
            </div>
            <div>
              <p className="text-[12px] font-mono font-semibold text-foreground">New Project</p>
              <p className="text-[10px] font-mono text-muted-foreground">
                {step === 1 ? "Provide basic project information" : "Upload the plan to compute"}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent press-scale shrink-0"
          >
            <X size={13} />
          </button>
        </div>

        {/* Step progress */}
        <div className="flex items-center gap-2 px-6 pt-4">
          {[1, 2].map((s) => (
            <div key={s} className="flex-1 h-[2px] rounded-full bg-accent overflow-hidden">
              <div
                className="h-full bg-foreground transition-all duration-500 ease-out"
                style={{ width: step >= s ? "100%" : "0%" }}
              />
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between px-6 pt-2 pb-1">
          <Mono className={step === 1 ? "text-foreground" : "opacity-50"}>01 Details</Mono>
          <Mono className={step === 2 ? "text-foreground" : "opacity-50"}>02 Upload</Mono>
        </div>

        {/* Body */}
        <div className="p-6 min-h-[300px]">
          {step === 1 ? (
            <div className="space-y-5 animate-slide-left">
              <FieldWrap label="Project Name" hint="Give your project a clear and unique name">
                <input
                  autoFocus
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Smith Home, Hospital 1 Project"
                  className="w-full h-9 bg-background border border-border rounded-lg px-3 text-[11px] font-mono text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-foreground/30 focus:shadow-[0_0_0_3px_rgba(255,255,255,0.06)] transition-all"
                />
              </FieldWrap>
              <FieldWrap label="Description" hint="Optional — helps you identify this project later">
                <TxtArea value={desc} onChange={setDesc} placeholder="e.g. Private Home, Modern Residential" rows={3} />
              </FieldWrap>
              <div>
                <Mono className="block mb-2.5">Plan Type</Mono>
                <div className="grid grid-cols-3 gap-2">
                  {PLAN_TYPES.map(({ id, Icon }) => (
                    <button
                      key={id}
                      onClick={() => setPlanType(id)}
                      className={`flex flex-col items-center gap-2 py-4 border rounded-lg text-[10px] font-mono uppercase tracking-[0.06em] transition-all press-scale ${
                        planType === id
                          ? "border-foreground/40 text-foreground bg-accent"
                          : "border-border text-muted-foreground hover:border-foreground/20 hover:text-foreground"
                      }`}
                    >
                      <Icon size={15} strokeWidth={1.5} />
                      {id.replace(" Plan", "")}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="animate-slide-right">
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                onClick={() => inputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl flex flex-col items-center justify-center py-16 gap-4 cursor-pointer transition-all ${
                  dragging ? "border-foreground/50 bg-foreground/5 scale-[1.01]" : "border-border hover:border-foreground/20"
                }`}
              >
                <div
                  className={`w-14 h-14 border border-border rounded-xl flex items-center justify-center text-muted-foreground transition-transform duration-300 ${
                    dragging ? "scale-110" : ""
                  }`}
                >
                  <CloudUpload size={22} strokeWidth={1.5} />
                </div>

                {file ? (
                  <div className="flex items-center gap-2 px-3 py-1.5 border border-border rounded-lg bg-accent/40 animate-pop-in">
                    <Check size={12} className="text-foreground" />
                    <span className="text-[11px] font-mono text-foreground">{file.name}</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setFile(null);
                      }}
                      className="text-muted-foreground hover:text-foreground press-scale"
                    >
                      <X size={11} />
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="text-center">
                      <p className="text-[12px] font-mono text-muted-foreground mb-1">Drag and drop your plan file here</p>
                      <p className="text-[10px] font-mono text-muted-foreground/50">PNG, JPG, PDF supported</p>
                    </div>
                    <Btn
                      variant="secondary"
                      icon={<FolderOpen size={11} />}
                      onClick={(e) => {
                        e?.stopPropagation();
                        inputRef.current?.click();
                      }}
                    >
                      Select File
                    </Btn>
                  </>
                )}
                <input
                  ref={inputRef}
                  type="file"
                  className="hidden"
                  accept="image/*,.pdf"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setFile(f);
                  }}
                />
              </div>
              <p className="text-[10px] font-mono text-muted-foreground mt-4">
                ⓘ Make sure the plan image is clear and legible — {planType} selected.
              </p>
              {error && <p className="text-[11px] font-mono text-red-400 mt-3 animate-pop-in">{error}</p>}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-border bg-background/40">
          <div className="flex items-center gap-1.5">
            {[1, 2].map((s) => (
              <div key={s} className={`w-1.5 h-1.5 rounded-full transition-colors ${step === s ? "bg-foreground" : "bg-border"}`} />
            ))}
          </div>
          <div className="flex gap-2">
            {step === 1 ? (
              <>
                <Btn variant="ghost" onClick={onClose}>Cancel</Btn>
                <Btn
                  variant="secondary"
                  onClick={() => canContinueStep1 && setStep(2)}
                  icon={<ChevronRight size={11} />}
                  className={!canContinueStep1 ? "opacity-40 cursor-not-allowed" : ""}
                >
                  Continue
                </Btn>
              </>
            ) : (
              <>
                <Btn variant="ghost" onClick={() => setStep(1)} icon={<ChevronLeft size={11} />}>
                  Back
                </Btn>
                <Btn
                  variant="primary"
                  onClick={handleStart}
                  icon={<ChevronRight size={11} />}
                  className={!canStart ? "opacity-40 cursor-not-allowed" : ""}
                >
                  {starting ? "Starting…" : "Start Scan"}
                </Btn>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
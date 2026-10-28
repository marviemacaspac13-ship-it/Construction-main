import { useCallback, useEffect, useRef, useState } from "react";
import {
  CloudUpload, FolderOpen, Check, ChevronRight, ArrowLeft, X,
  FileText, LayoutDashboard, Zap, Layers,
} from "lucide-react";
import { SectionBar, Btn, Mono } from "../components/ui";
import { useLocation, useNavigate } from "react-router";
import type { ProjectDraft } from "../../lib/projects";
import { DEFAULT_WALL_HEIGHT_M } from "../../lib/wall-height";
import { planFileError } from "../../lib/plan-assets";
import { uploadTips } from "../../lib/upload-guidance";

/**
 * `projectId` is set only when coming BACK here from a failed scan. The
 * project already exists in that case and must be reused, or a retry files
 * a second row for the same drawing.
 */
type NavState = { draft?: ProjectDraft; projectId?: string; expectedRevision?: string | null };

// Same trio used on the Details screen, so the icon/color for a plan type is
// consistent everywhere it shows up in the wizard. Tips: lib/upload-guidance.
const PLAN_META: Record<string, { Icon: typeof LayoutDashboard; color: string; dot: string }> = {
  "Floor Plan": {
    Icon: LayoutDashboard,
    color: "text-sky-400",
    dot: "bg-sky-400",
  },
  "Electrical Plan": {
    Icon: Zap,
    color: "text-orange-400",
    dot: "bg-orange-400",
  },
  "Plumbing Plan": {
    Icon: Layers,
    color: "text-emerald-400",
    dot: "bg-emerald-400",
  },
};

const STEPS = ["Details", "Upload", "Scan"];

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function UploadScreen() {
  const navigate = useNavigate();
  const location = useLocation();
  const { draft, projectId, expectedRevision } = (location.state ?? {}) as NavState;
  const name = draft?.name;
  const description = draft?.description;
  const planType = draft?.planType;

  const meta = PLAN_META[planType ?? "Floor Plan"] ?? PLAN_META["Floor Plan"];

  const [dragging, setDragging] = useState(false);
  const [file, setFile]         = useState<File | null>(null);
  const [fileError, setFileError] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const inputRef                = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!file || !file.type.startsWith("image/")) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const acceptFile = (f: File) => {
    setFileError("");
    const error = planFileError(f);
    if (error) {
      setFileError(error);
      setFile(null);
      return;
    }
    setFile(f);
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) acceptFile(f);
  }, []);

  const handleContinue = () => {
    if (!draft) {
      // Reached this screen without going through project creation first.
      navigate("/projects/details");
      return;
    }
    if (!file) return;
    navigate("/scanning", { state: { draft, projectId, file, expectedRevision } });
  };

  const goBack = () => {
    // Carry the draft back so re-visiting Details doesn't lose what was typed.
    navigate("/projects/details", { state: { draft, projectId } });
  };

  return (
    <div className="h-full flex flex-col animate-page-in">
      {/* Header row */}
      <div className="flex items-center justify-between px-10 pt-8 pb-6 shrink-0">
        <SectionBar>Upload Plan</SectionBar>

        <div className="flex items-center gap-2.5">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-2.5">
              <div className={`flex items-center gap-1.5 ${i === 1 ? "text-foreground" : i < 1 ? "text-muted-foreground/70" : "text-muted-foreground/45"}`}>
                <span className="text-[10px] font-mono">{i < 1 ? <Check size={10} /> : String(i + 1).padStart(2, "0")}</span>
                <span className="text-[10px] font-mono uppercase tracking-[0.14em]">{s}</span>
              </div>
              {i < STEPS.length - 1 && <div className="w-7 h-px bg-border" />}
            </div>
          ))}
        </div>
      </div>

      {!draft && (
        <p className="text-[11px] font-mono text-orange-400 mb-4 px-10 animate-pop-in shrink-0">
          No project selected — go back and create one first.
        </p>
      )}

      {/* Body — fills the rest of the viewport that isn't the top bar / side nav */}
      {planType==='Electrical Plan'&&<div className="mx-10 mb-5 text-sm space-y-2"><p>Review device locations and types before confirming your estimate.</p><p className="text-muted-foreground">Includes wire and conduit allowances for supported lights and convenience outlets. Switch and AC wiring, breakers, panels and circuit design are excluded.</p></div>}
      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-6 px-10 pb-6 overflow-y-auto">
        {/* Left: dropzone */}
        <div className="border border-border rounded-xl bg-card flex flex-col overflow-hidden">
          <div className="flex items-center gap-4 px-7 py-5 border-b border-border shrink-0">
            <div className="w-9 h-9 border border-border rounded-lg flex items-center justify-center text-muted-foreground">
              <CloudUpload size={15} />
            </div>
            <div>
              <p className="text-[13px] font-mono font-semibold text-foreground">Plan File</p>
              <p className="text-[10px] font-mono text-muted-foreground">Upload the {planType ?? "Floor Plan"} you want scanned</p>
            </div>
          </div>

          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => !file && inputRef.current?.click()}
            className={`flex-1 border-2 border-dashed rounded-xl m-6 flex flex-col items-center justify-center gap-5 transition-colors ${
              file ? "cursor-default" : "cursor-pointer"
            } ${dragging ? "border-foreground/40 bg-foreground/5" : "border-border hover:border-foreground/20"}`}
          >
            {file ? (
              <div className="flex flex-col items-center gap-4 px-6 animate-pop-in max-w-full">
                {previewUrl ? (
                  <img src={previewUrl} alt="Plan preview" className="max-h-64 max-w-full rounded-lg border border-border object-contain" />
                ) : (
                  <div className="w-16 h-16 border border-border rounded-xl flex items-center justify-center text-muted-foreground">
                    <FileText size={24} strokeWidth={1.5} />
                  </div>
                )}
                <div className="flex items-center gap-3">
                  <div className="text-center">
                    <div className="flex items-center gap-1.5 justify-center">
                      <Check size={12} className="text-emerald-400 shrink-0" />
                      <span className="text-[12px] font-mono text-foreground truncate max-w-[280px]">{file.name}</span>
                    </div>
                    <p className="text-[10px] font-mono text-muted-foreground mt-0.5">{formatBytes(file.size)}</p>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); setFile(null); setFileError(""); }}
                    className="w-6 h-6 rounded-full border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent press-scale shrink-0"
                  >
                    <X size={11} />
                  </button>
                </div>
                <Btn variant="ghost" icon={<FolderOpen size={11} />} onClick={(e) => { e?.stopPropagation(); inputRef.current?.click(); }}>
                  Choose a different file
                </Btn>
              </div>
            ) : (
              <>
                <div className="w-16 h-16 border border-border rounded-xl flex items-center justify-center text-muted-foreground">
                  <CloudUpload size={24} strokeWidth={1.5} />
                </div>
                <div className="text-center">
                  <p className="text-[13px] font-mono text-muted-foreground mb-1">Drag and drop your plan here</p>
                  <p className="text-[10px] font-mono text-muted-foreground">PNG, JPG or WebP — up to 25 MB</p>
                </div>
                <Btn variant="secondary" icon={<FolderOpen size={11} />} onClick={(e) => { e?.stopPropagation(); inputRef.current?.click(); }}>
                  Select File
                </Btn>
              </>
            )}
            <input
              ref={inputRef}
              type="file"
              className="hidden"
              accept="image/png,image/jpeg,image/webp"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) acceptFile(f); e.target.value = ""; }}
            />
          </div>

          {fileError && (
            <p className="text-[11px] font-mono text-red-400 px-7 pb-5 -mt-2 animate-pop-in shrink-0">{fileError}</p>
          )}
        </div>

        {/* Right: project summary + guidance */}
        <div className="flex flex-col gap-6 min-h-0">
          <div className="border border-border rounded-xl bg-card p-6 shrink-0">
            <Mono className="block mb-3">Project</Mono>
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-lg border border-current flex items-center justify-center shrink-0 ${meta.color}`}>
                <meta.Icon size={16} strokeWidth={1.5} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-semibold text-foreground truncate">{name || "Untitled Project"}</p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                  <span className={`text-[10px] font-mono ${meta.color}`}>{planType ?? "Floor Plan"}</span>
                </div>
              </div>
            </div>
            {description && (
              <p className="text-[11px] font-mono text-muted-foreground mt-3 leading-relaxed line-clamp-3">{description}</p>
            )}
            {planType === "Floor Plan" && (
              <p className="text-sm text-muted-foreground mt-3">
                Wall height: {(draft?.wallHeightM ?? DEFAULT_WALL_HEIGHT_M).toFixed(2)} m · All walls
              </p>
            )}
            {planType === 'Plumbing Plan' && <p className="text-sm text-muted-foreground mt-3">Check every plumbing fixture location and count before confirming your estimate.</p>}
          </div>

          <div className="border border-border rounded-xl bg-card p-6 flex-1 overflow-y-auto">
            <Mono className="block mb-4">For a clean scan</Mono>
            <ul className="space-y-3">
              {uploadTips(planType ?? "Floor Plan").map((tip, i) => (
                <li key={i} className="flex items-start gap-2.5">
                  <span className={`w-1 h-1 rounded-full mt-2 shrink-0 ${meta.dot}`} />
                  <span className="text-[11px] font-mono text-muted-foreground leading-relaxed">{tip}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Footer — pinned full width across the content area */}
      <div className="flex items-center justify-between px-10 py-5 border-t border-border bg-background/40 shrink-0">
        <p className="text-[10px] font-mono text-muted-foreground flex items-center gap-1.5">
          <span className="opacity-60">ⓘ</span> Please make sure the plan image is clear and legible.
        </p>
        <div className="flex gap-2">
          <Btn variant="ghost" onClick={goBack} icon={<ArrowLeft size={11} />}>Go Back</Btn>
          <Btn variant="primary" onClick={handleContinue} icon={<ChevronRight size={11} />} disabled={!file}>
            Continue
          </Btn>
        </div>
      </div>
    </div>
  );
}

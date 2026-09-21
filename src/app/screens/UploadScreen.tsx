import { useCallback, useRef, useState } from "react";
import { CloudUpload, FolderOpen, Check, ChevronRight, ArrowLeft } from "lucide-react";
import { SectionBar, Btn } from "../components/ui";
import { useLocation, useNavigate } from "react-router";
import type { ProjectDraft } from "../../lib/projects";

/**
 * `projectId` is set only when coming BACK here from a failed scan. The
 * project already exists in that case and must be reused, or a retry files
 * a second row for the same drawing.
 */
type NavState = { draft?: ProjectDraft; projectId?: string };

export function UploadScreen() {
  const navigate = useNavigate();
  const location = useLocation();
  const { draft, projectId } = (location.state ?? {}) as NavState;

  const [dragging, setDragging] = useState(false);
  const [file, setFile]         = useState<File | null>(null);
  const inputRef                = useRef<HTMLInputElement>(null);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) setFile(f);
  }, []);

  const handleContinue = () => {
    if (!draft) {
      // Reached this screen without going through the details form first.
      navigate("/projects/details");
      return;
    }
    if (!file) return;
    navigate("/scanning", { state: { draft, projectId, file } });
  };

  return (
    <div className="p-10 max-w-2xl animate-page-in">
      <SectionBar>Upload Plan</SectionBar>

      {!draft && (
        <p className="text-[11px] font-mono text-orange-400 mb-4 animate-pop-in">
          No project details yet — go back and fill them in first.
        </p>
      )}

      <div className="border border-border rounded-lg bg-card overflow-hidden">
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl m-6 flex flex-col items-center justify-center py-24 gap-5 cursor-pointer transition-colors ${
            dragging ? "border-foreground/40 bg-foreground/5" : "border-border hover:border-foreground/20"
          }`}
        >
          <div className="w-16 h-16 border border-border rounded-xl flex items-center justify-center text-muted-foreground">
            <CloudUpload size={24} strokeWidth={1.5} />
          </div>

          {file ? (
            <div className="flex items-center gap-2">
              <Check size={12} className="text-foreground" />
              <span className="text-[12px] font-mono text-foreground">{file.name}</span>
            </div>
          ) : (
            <>
              <div className="text-center">
                <p className="text-[13px] font-mono text-muted-foreground mb-1">Drag and drop your image file here</p>
                <p className="text-[10px] font-mono text-muted-foreground/50">PNG, JPG, PDF supported</p>
              </div>
              <Btn variant="secondary" icon={<FolderOpen size={11} />} onClick={(e) => { e?.stopPropagation(); inputRef.current?.click(); }}>
                Select File
              </Btn>
            </>
          )}
          <input ref={inputRef} type="file" className="hidden" accept="image/*,.pdf" onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile(f); }} />
        </div>

        <div className="flex items-center justify-between px-6 py-4 border-t border-border">
          <p className="text-[10px] font-mono text-muted-foreground">ⓘ Please make sure the plan image is clear and legible.</p>
          <div className="flex gap-2">
            <Btn
              variant="ghost"
              onClick={() => navigate("/projects/details", { state: { draft } })}
              icon={<ArrowLeft size={11} />}
            >
              Go Back
            </Btn>
            <Btn variant="secondary" onClick={handleContinue} icon={<ChevronRight size={11} />} disabled={!file}>
              Continue
            </Btn>
          </div>
        </div>
      </div>
    </div>
  );
}

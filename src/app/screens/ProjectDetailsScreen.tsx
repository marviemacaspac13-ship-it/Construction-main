import { useState } from "react";
import { FolderOpen, ChevronRight, LayoutDashboard, Zap, Layers } from "lucide-react";
import { SectionBar, Btn, FieldWrap, Mono } from "../components/ui";
import { useLocation, useNavigate } from "react-router";

// Mirrors the trade split the backend actually reads each plan type with -
// OCR'd dimension chains, symbol-library matching, or printed fixture tags -
// so the copy here sets accurate expectations before a file is even chosen.
const PLAN_TYPES = [
  {
    id: "Floor Plan",
    Icon: LayoutDashboard,
    color: "text-sky-400",
    dot: "bg-sky-400",
    tagline: "Printed room dimensions",
    detail: "Reads the dimension chains off the sheet and derives room areas and wall lengths from them.",
  },
  {
    id: "Electrical Plan",
    Icon: Zap,
    color: "text-orange-400",
    dot: "bg-orange-400",
    tagline: "Symbol matching",
    detail: "Matches devices against your Symbol Library to count outlets, switches, and fixtures.",
  },
  {
    id: "Plumbing Plan",
    Icon: Layers,
    color: "text-emerald-400",
    dot: "bg-emerald-400",
    tagline: "Fixture tag counts",
    detail: "Counts printed fixture tags (WC, LAV, FD) and derives the pipework that serves them.",
  },
] as const;

const STEPS = ["Details", "Upload", "Scan"];

/** Carried in navigation state so a draft survives going back and forth
 *  between Details and Upload without ever touching the database. */
type DraftState = {
  projectId?: string; // only set once a prior scan attempt already created the row (see ScanningScreen)
  name?: string;
  description?: string;
  planType?: string;
};

export function ProjectDetailsScreen() {
  const navigate = useNavigate();
  const location = useLocation();
  const draft = (location.state ?? {}) as DraftState;

  const [title, setTitle]       = useState(draft.name ?? "");
  const [desc, setDesc]         = useState(draft.description ?? "");
  const [planType, setPlanType] = useState(draft.planType ?? "Floor Plan");
  const [error, setError]       = useState("");

  const selected = PLAN_TYPES.find((p) => p.id === planType) ?? PLAN_TYPES[0];

  // Nothing is written to the database here. This step only collects the
  // draft and hands it to Upload; the project row itself isn't created
  // until a scan actually starts (see ScanningScreen), so abandoning the
  // wizard part-way through never leaves an orphaned "processing" project.
  const handleContinue = () => {
    if (!title.trim()) {
      setError("Give the project a name first.");
      return;
    }
    setError("");
    navigate("/upload", {
      state: { projectId: draft.projectId, name: title.trim(), description: desc.trim(), planType },
    });
  };

  return (
    <div className="h-full flex flex-col animate-page-in">
      {/* Header row */}
      <div className="flex items-center justify-between px-10 pt-8 pb-6 shrink-0">
        <SectionBar>New Project</SectionBar>

        <div className="flex items-center gap-2.5">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-2.5">
              <div className={`flex items-center gap-1.5 ${i === 0 ? "text-foreground" : "text-muted-foreground/45"}`}>
                <span className="text-[10px] font-mono">{String(i + 1).padStart(2, "0")}</span>
                <span className="text-[10px] font-mono uppercase tracking-[0.14em]">{s}</span>
              </div>
              {i < STEPS.length - 1 && <div className="w-7 h-px bg-border" />}
            </div>
          ))}
        </div>
      </div>

      {/* Body — fills the rest of the viewport that isn't the top bar / side nav */}
      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-6 px-10 pb-6 overflow-y-auto">
        {/* Left: form */}
        <div className="border border-border rounded-xl bg-card flex flex-col overflow-hidden">
          <div className="flex items-center gap-4 px-7 py-5 border-b border-border shrink-0">
            <div className="w-9 h-9 border border-border rounded-lg flex items-center justify-center text-muted-foreground">
              <FolderOpen size={15} />
            </div>
            <div>
              <p className="text-[13px] font-mono font-semibold text-foreground">Project Details</p>
              <p className="text-[10px] font-mono text-muted-foreground">Provide basic information about your project</p>
            </div>
          </div>

          <div className="flex-1 p-7 flex flex-col gap-7">
            <FieldWrap label="Project Name" hint="Give your project a clear and unique name">
              <input
                autoFocus
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Smith Home, Hospital 1 Project"
                className="w-full h-11 bg-background border border-border rounded-lg px-4 text-[13px] font-mono text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-foreground/30 focus:shadow-[0_0_0_3px_rgba(255,255,255,0.06)] transition-all"
              />
            </FieldWrap>

            <div className="flex-1 flex flex-col min-h-0">
              <FieldWrap label="Description" hint="Add a brief description that best identifies this project">
                <textarea
                  value={desc}
                  onChange={(e) => setDesc(e.target.value)}
                  placeholder="e.g. Private Home, Modern Residential"
                  className="w-full flex-1 min-h-[180px] bg-background border border-border rounded-lg px-4 py-3 text-[12px] font-mono text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-foreground/30 focus:shadow-[0_0_0_3px_rgba(255,255,255,0.06)] transition-all resize-none"
                />
              </FieldWrap>
            </div>

            {error && <p className="text-[11px] font-mono text-red-400 animate-pop-in shrink-0">{error}</p>}
          </div>
        </div>

        {/* Right: plan type + live preview */}
        <div className="flex flex-col gap-6 min-h-0">
          <div className="border border-border rounded-xl bg-card p-6 flex-1 overflow-y-auto">
            <Mono className="block mb-4">Select Plan Type</Mono>
            <div className="space-y-3">
              {PLAN_TYPES.map(({ id, Icon, color, tagline, detail }) => {
                const active = planType === id;
                return (
                  <button
                    key={id}
                    onClick={() => setPlanType(id)}
                    className={`w-full text-left p-4 border rounded-xl transition-all duration-200 press-scale ${
                      active ? `border-current bg-white/[0.03] ${color}` : "border-border hover:border-foreground/20 hover:bg-accent/20"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3 min-w-0">
                        <div
                          className={`w-9 h-9 rounded-lg border flex items-center justify-center shrink-0 ${
                            active ? "border-current" : "border-border text-muted-foreground"
                          }`}
                        >
                          <Icon size={15} strokeWidth={1.5} />
                        </div>
                        <div className="min-w-0">
                          <p className={`text-[12px] font-mono font-semibold truncate ${active ? "text-foreground" : "text-muted-foreground"}`}>
                            {id}
                          </p>
                          <p className={`text-[10px] font-mono mt-0.5 ${active ? color : "text-muted-foreground/60"}`}>{tagline}</p>
                        </div>
                      </div>
                      <div
                        className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center shrink-0 mt-0.5 ${
                          active ? "border-foreground bg-foreground" : "border-muted-foreground"
                        }`}
                      >
                        {active && <div className="w-1.5 h-1.5 rounded-full bg-background" />}
                      </div>
                    </div>
                    {active && (
                      <p className="text-[10px] font-mono text-muted-foreground mt-3 pl-12 leading-relaxed animate-pop-in">
                        {detail}
                      </p>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Live preview of the project about to be created */}
          <div className="border border-border rounded-xl bg-card p-6 shrink-0">
            <Mono className="block mb-3">Preview</Mono>
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-lg border border-current flex items-center justify-center shrink-0 ${selected.color}`}>
                <selected.Icon size={16} strokeWidth={1.5} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-semibold text-foreground truncate">{title.trim() || "Untitled Project"}</p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${selected.dot}`} />
                  <span className={`text-[10px] font-mono ${selected.color}`}>{selected.id}</span>
                </div>
              </div>
            </div>
            {desc.trim() && (
              <p className="text-[11px] font-mono text-muted-foreground mt-3 leading-relaxed line-clamp-3">{desc}</p>
            )}
          </div>
        </div>
      </div>

      {/* Footer — pinned full width across the content area */}
      <div className="flex items-center justify-between px-10 py-5 border-t border-border bg-background/40 shrink-0">
        <p className="text-[10px] font-mono text-muted-foreground flex items-center gap-1.5">
          <span className="opacity-60">ⓘ</span> Make sure the plan type matches your uploaded file.
        </p>
        <div className="flex gap-2">
          <Btn variant="ghost" onClick={() => navigate("/projects")}>Cancel</Btn>
          <Btn variant="primary" onClick={handleContinue} icon={<ChevronRight size={12} />}>
            Continue
          </Btn>
        </div>
      </div>
    </div>
  );
}
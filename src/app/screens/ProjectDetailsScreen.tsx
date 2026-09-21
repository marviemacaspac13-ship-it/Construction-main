import { useState } from "react";
import { FolderOpen, ChevronRight, LayoutDashboard, Zap, Layers } from "lucide-react";
import { SectionBar, Btn, FieldWrap, TxtArea, Mono } from "../components/ui";
import { useLocation, useNavigate } from "react-router";
import type { ProjectDraft } from "../../lib/projects";

type NavState = { draft?: ProjectDraft };

export function ProjectDetailsScreen() {
  const navigate = useNavigate();
  const location = useLocation();
  // Coming back from Upload returns the draft, so a change of mind does not
  // cost the user everything they typed.
  const { draft } = (location.state ?? {}) as NavState;

  const [title, setTitle]       = useState(draft?.name ?? "");
  const [desc, setDesc]         = useState(draft?.description ?? "");
  const [planType, setPlanType] = useState(draft?.planType ?? "Floor Plan");
  const [error, setError]       = useState("");

  const plans = [
    { id: "Floor Plan",      Icon: LayoutDashboard },
    { id: "Electrical Plan", Icon: Zap },
    { id: "Plumbing Plan",   Icon: Layers },
  ];

  /**
   * Carries the details forward WITHOUT writing anything.
   *
   * This used to insert the project here and hand Upload an id, which meant
   * every abandoned flow left a row stuck at "Scanning..." for ever.
   * ScanningScreen creates it now, once there is a file to scan.
   */
  const handleContinue = () => {
    if (!title.trim()) {
      setError("Give the project a name first.");
      return;
    }
    setError("");
    const next: ProjectDraft = {
      name: title.trim(),
      description: desc.trim(),
      planType,
    };
    navigate("/upload", { state: { draft: next } });
  };

  return (
    <div className="p-10 max-w-3xl animate-page-in">
      <SectionBar>New Project</SectionBar>

      <div className="border border-border rounded-lg bg-card overflow-hidden">
        <div className="flex items-center gap-4 px-6 py-4 border-b border-border">
          <div className="w-8 h-8 border border-border rounded-lg flex items-center justify-center text-muted-foreground">
            <FolderOpen size={14} />
          </div>
          <div>
            <p className="text-[12px] font-mono font-semibold text-foreground">Project Details</p>
            <p className="text-[10px] font-mono text-muted-foreground">Provide basic information about your project</p>
          </div>
        </div>

        <div className="flex gap-10 p-6">
          <div className="flex-1 space-y-5">
            <FieldWrap label="Project Name" hint="Give your project a clear and unique name">
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Smith Home, Hospital 1 Project"
                className="w-full h-8 bg-background border border-border rounded-lg px-3 text-[11px] font-mono text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-foreground/25 transition-colors"
              />
            </FieldWrap>
            <FieldWrap label="Description" hint="Add a brief description that best identifies this project">
              <TxtArea value={desc} onChange={setDesc} placeholder="e.g. Private Home, Modern Residential" rows={5} />
            </FieldWrap>
            {error && <p className="text-[11px] font-mono text-red-400 animate-pop-in">{error}</p>}
          </div>

          <div className="w-52 shrink-0">
            <Mono className="block mb-3">Select Plan Type</Mono>
            <div className="space-y-2.5">
              {plans.map(({ id, Icon }) => (
                <button
                  key={id}
                  onClick={() => setPlanType(id)}
                  className={`w-full flex items-center justify-between px-4 py-4 border rounded-lg text-[11px] font-mono transition-colors ${
                    planType === id ? "border-foreground/40 text-foreground bg-accent" : "border-border text-muted-foreground hover:border-foreground/20 hover:text-foreground"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon size={13} strokeWidth={1.5} />
                    <span>{id}</span>
                  </div>
                  <div className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center shrink-0 ${planType === id ? "border-foreground bg-foreground" : "border-muted-foreground"}`}>
                    {planType === id && <div className="w-1.5 h-1.5 rounded-full bg-background" />}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between px-6 py-4 border-t border-border">
          <p className="text-[10px] font-mono text-muted-foreground">ⓘ Make sure the plan type matches your uploaded file.</p>
          <div className="flex gap-2">
            <Btn variant="ghost" onClick={() => navigate("/projects")}>Cancel</Btn>
            <Btn variant="secondary" onClick={handleContinue} icon={<ChevronRight size={11} />}>
              Continue
            </Btn>
          </div>
        </div>
      </div>
    </div>
  );
}

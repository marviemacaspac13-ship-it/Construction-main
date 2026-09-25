import { useEffect, useState } from "react";
import { Search, ChevronDown, MoreVertical, Plus, LayoutGrid, Zap, Layers, Loader2, Check, Pencil, Trash2, X } from "lucide-react";
import { listProjects, deleteProject, renameProject, type Project } from "../../lib/projects";
import { useNavigate } from "react-router";

const TYPE_ICON: Record<string, typeof LayoutGrid> = {
  "Floor Plan": LayoutGrid,
  "Electrical Plan": Zap,
  "Plumbing Plan": Layers,
};

const TYPE_COLOR: Record<string, string> = {
  "Floor Plan": "text-sky-400",
  "Electrical Plan": "text-orange-400",
  "Plumbing Plan": "text-emerald-400",
};

const PLAN_TYPE_OPTIONS = ["All Types", "Floor Plan", "Electrical Plan", "Plumbing Plan"];
const DATE_OPTIONS = [
  { id: "newest", label: "Newest First" },
  { id: "oldest", label: "Oldest First" },
] as const;
type DateSort = (typeof DATE_OPTIONS)[number]["id"];

/** A small dropdown shared by the Plan Type and Date filters — click-outside
 *  and Escape both close it, matching the pattern already used for the
 *  profile menu in AppShell. */
function FilterDropdown({
  label,
  options,
  active,
  isActive,
  onSelect,
  open,
  onToggle,
}: {
  label: string;
  options: { id: string; text: string }[];
  active: string;
  isActive: (id: string) => boolean;
  onSelect: (id: string) => void;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="relative">
      <button
        onClick={onToggle}
        className={`flex items-center gap-1.5 h-9 px-3 border rounded-lg text-[11px] font-mono transition-colors ${
          open || active !== "" ? "text-foreground border-foreground/30 bg-accent" : "text-muted-foreground border-border hover:text-foreground hover:bg-accent"
        }`}
      >
        {label}<ChevronDown size={11} className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={onToggle} />
          <div className="absolute left-0 top-11 w-44 bg-popover border border-border rounded-lg overflow-hidden z-50 shadow-lg animate-pop-in origin-top-left">
            {options.map((o) => (
              <button
                key={o.id}
                onClick={() => onSelect(o.id)}
                className="w-full flex items-center justify-between gap-2 px-4 py-2.5 text-[11px] font-mono text-foreground hover:bg-accent transition-colors border-b border-border last:border-b-0"
              >
                {o.text}
                {isActive(o.id) && <Check size={11} className="text-foreground shrink-0" />}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export function ProjectsScreen() {
  const navigate = useNavigate();
  const [search, setSearch]         = useState("");
  const [menu, setMenu]             = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameError, setRenameError] = useState("");
  const [openFilter, setOpenFilter] = useState<"planType" | "date" | null>(null);
  const [planTypeFilter, setPlanTypeFilter] = useState("All Types");
  const [dateSort, setDateSort]     = useState<DateSort>("newest");
  const [projects, setProjects]     = useState<Project[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState("");

  const refresh = () => {
    setLoading(true);
    listProjects()
      .then(setProjects)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load projects."))
      .finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, []);

  const filtered = projects
    .filter((p) => p.name.toLowerCase().includes(search.toLowerCase()))
    .filter((p) => planTypeFilter === "All Types" || p.plan_type === planTypeFilter)
    .sort((a, b) => {
      const diff = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      return dateSort === "newest" ? -diff : diff;
    });

  const closeMenu = () => { setMenu(null); setConfirmDeleteId(null); };

  const handleRemove = async (id: string) => {
    closeMenu();
    setProjects((pp) => pp.filter((x) => x.id !== id)); // optimistic
    try {
      await deleteProject(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete project.");
      refresh(); // roll back on failure
    }
  };

  const startRename = (p: Project) => {
    closeMenu();
    setRenameError("");
    setRenameValue(p.name);
    setRenamingId(p.id);
  };

  const cancelRename = () => {
    setRenamingId(null);
    setRenameError("");
  };

  const saveRename = async (id: string) => {
    const original = projects.find((p) => p.id === id)?.name ?? "";
    const trimmed = renameValue.trim();
    if (!trimmed) {
      setRenameError("Project name can't be empty.");
      return;
    }
    if (trimmed === original) {
      setRenamingId(null);
      return;
    }
    setRenamingId(null);
    setProjects((pp) => pp.map((p) => (p.id === id ? { ...p, name: trimmed } : p))); // optimistic
    try {
      await renameProject(id, trimmed);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to rename project.");
      setProjects((pp) => pp.map((p) => (p.id === id ? { ...p, name: original } : p))); // roll back
    }
  };

  const openProject = (p: Project) => {
    if (p.status === "processing") return; // nothing to show yet
    navigate("/results", { state: { projectId: p.id } });
  };

  return (
    <div className="p-10 animate-page-in">
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-[26px] font-semibold text-foreground leading-tight">Projects</h1>
          <p className="text-[12px] font-mono text-muted-foreground mt-1">{projects.length} projects total</p>
        </div>
        <button
          onClick={() => navigate("/projects/details")}
          className="h-10 px-5 rounded-lg bg-foreground text-background text-[11px] font-mono tracking-[0.14em] uppercase flex items-center gap-2 press-scale"
        >
          <Plus size={13} /> New Project
        </button>
      </div>

      <div className="flex items-center gap-3 mb-6">
        <div className="flex items-center h-9 border border-border rounded-lg px-3 gap-2 w-56 focus-within:border-foreground/25 transition-colors">
          <Search size={12} className="text-muted-foreground shrink-0" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search projects"
            className="bg-transparent text-[12px] font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none flex-1"
          />
        </div>
        <FilterDropdown
          label={planTypeFilter === "All Types" ? "Plan Type" : planTypeFilter}
          options={PLAN_TYPE_OPTIONS.map((t) => ({ id: t, text: t }))}
          active={planTypeFilter === "All Types" ? "" : planTypeFilter}
          isActive={(id) => id === planTypeFilter}
          onSelect={(id) => { setPlanTypeFilter(id); setOpenFilter(null); }}
          open={openFilter === "planType"}
          onToggle={() => setOpenFilter(openFilter === "planType" ? null : "planType")}
        />
        <FilterDropdown
          label={dateSort === "newest" ? "Date" : "Oldest First"}
          options={DATE_OPTIONS.map((o) => ({ id: o.id, text: o.label }))}
          active={dateSort === "newest" ? "" : dateSort}
          isActive={(id) => id === dateSort}
          onSelect={(id) => { setDateSort(id as DateSort); setOpenFilter(null); }}
          open={openFilter === "date"}
          onToggle={() => setOpenFilter(openFilter === "date" ? null : "date")}
        />
      </div>

      {error && <p className="text-[11px] font-mono text-red-400 mb-4">{error}</p>}

      {loading ? (
        <p className="text-[12px] font-mono text-muted-foreground flex items-center gap-2">
          <Loader2 size={12} className="animate-spin-slow" /> Loading projects…
        </p>
      ) : (
        <div className="grid grid-cols-3 gap-5">
          <button
            onClick={() => navigate("/projects/details")}
            className="border border-dashed border-border rounded-xl flex flex-col items-center justify-center gap-2 hover:border-foreground/25 hover:bg-accent/15 hover-lift transition-all group min-h-[160px]"
          >
            <Plus size={18} className="text-muted-foreground group-hover:text-foreground transition-colors" />
            <span className="text-[12px] font-mono tracking-[0.14em] uppercase text-muted-foreground group-hover:text-foreground transition-colors">
              New Project
            </span>
          </button>

          {filtered.map((p, i) => {
            const Icon = TYPE_ICON[p.plan_type] ?? LayoutGrid;
            const color = TYPE_COLOR[p.plan_type] ?? "text-muted-foreground";
            return (
              <div key={p.id} className="relative">
                <div
                  className="border border-border rounded-xl bg-card hover:bg-accent/40 hover-lift animate-stagger border-beam transition-colors p-6 flex flex-col min-h-[160px]"
                  style={{ animationDelay: `${i * 50}ms` }}
                >
                <div className="border-beam-content flex flex-col flex-1">
                  <div className="w-10 h-10 border border-border rounded-lg flex items-center justify-center text-foreground mb-4">
                    <Icon size={16} />
                  </div>

                  {renamingId === p.id ? (
                    <div className="flex-1" onClick={(e) => e.stopPropagation()}>
                      <input
                        autoFocus
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") saveRename(p.id);
                          if (e.key === "Escape") cancelRename();
                        }}
                        className="w-full h-8 bg-background border border-foreground/30 rounded-lg px-2.5 text-[14px] font-semibold text-foreground focus:outline-none focus:shadow-[0_0_0_3px_rgba(255,255,255,0.06)] transition-all"
                      />
                      {renameError && <p className="text-[10px] font-mono text-red-400 mt-1.5">{renameError}</p>}
                      <div className="flex gap-1.5 mt-2">
                        <button
                          onClick={() => saveRename(p.id)}
                          className="h-6 px-2.5 rounded border border-border text-[10px] font-mono text-foreground hover:bg-accent press-scale flex items-center gap-1 transition-colors"
                        >
                          <Check size={10} /> Save
                        </button>
                        <button
                          onClick={cancelRename}
                          className="h-6 px-2.5 rounded border border-transparent text-[10px] font-mono text-muted-foreground hover:bg-accent press-scale flex items-center gap-1 transition-colors"
                        >
                          <X size={10} /> Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button onClick={() => openProject(p)} className="text-left flex-1">
                      <p className="text-[16px] font-semibold text-foreground mb-1">{p.name}</p>
                      <p className={`text-[12px] font-mono ${color}`}>{p.plan_type}</p>
                      {p.status === "processing" && (
                        <p className="text-[10px] font-mono text-muted-foreground mt-1 flex items-center gap-1">
                          <Loader2 size={9} className="animate-spin-slow" /> Scanning…
                        </p>
                      )}
                      {p.status === "error" && (
                        <p className="text-[10px] font-mono text-red-400 mt-1">Scan failed</p>
                      )}
                    </button>
                  )}

                  <div className="flex items-center justify-between mt-4">
                    <span className="text-[11px] font-mono text-muted-foreground">
                      {new Date(p.created_at).toLocaleDateString()}
                    </span>
                    <button
                      onClick={() => setMenu(menu === p.id ? null : p.id)}
                      className="text-muted-foreground hover:text-foreground press-scale"
                    >
                      <MoreVertical size={13} />
                    </button>
                  </div>
                </div>
                </div>

                {menu === p.id && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={closeMenu} />
                    <div className="absolute top-full mt-1 right-4 w-44 bg-popover border border-border rounded-lg overflow-hidden z-50 shadow-lg animate-pop-in origin-top-right">
                      {confirmDeleteId === p.id ? (
                        <div className="p-3.5">
                          <p className="text-[10px] font-mono text-muted-foreground mb-3 leading-relaxed">
                            Delete <span className="text-foreground">"{p.name}"</span>? This can't be undone.
                          </p>
                          <div className="flex gap-1.5">
                            <button
                              onClick={() => handleRemove(p.id)}
                              className="flex-1 h-7 rounded border border-red-900/50 text-[10px] font-mono text-red-400 hover:bg-red-950 press-scale transition-colors"
                            >
                              Delete
                            </button>
                            <button
                              onClick={() => setConfirmDeleteId(null)}
                              className="flex-1 h-7 rounded border border-border text-[10px] font-mono text-muted-foreground hover:bg-accent press-scale transition-colors"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <button
                            onClick={() => startRename(p)}
                            className="w-full flex items-center gap-2.5 text-left px-4 py-2.5 text-[11px] font-mono text-foreground hover:bg-accent border-b border-border transition-colors"
                          >
                            <Pencil size={11} className="text-muted-foreground shrink-0" /> Rename
                          </button>
                          <button
                            onClick={() => setConfirmDeleteId(p.id)}
                            className="w-full flex items-center gap-2.5 text-left px-4 py-2.5 text-[11px] font-mono text-red-400 hover:bg-red-950/40 transition-colors"
                          >
                            <Trash2 size={11} className="shrink-0" /> Delete
                          </button>
                        </>
                      )}
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
import { useEffect, useState } from "react";
import { Search, ChevronDown, MoreVertical, Plus, LayoutGrid, Zap, Layers, Loader2 } from "lucide-react";
import { listProjects, deleteProject, type Project } from "../../lib/projects";
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

export function ProjectsScreen() {
  const navigate = useNavigate();
  const [search, setSearch]     = useState("");
  const [menu, setMenu]         = useState<string | null>(null);
  // Deleting a project takes its estimate with it and Supabase keeps no
  // copy, so the menu asks once rather than acting on the first click.
  const [confirm, setConfirm]   = useState<string | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState("");

  const refresh = () => {
    setLoading(true);
    listProjects()
      .then(setProjects)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load projects."))
      .finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, []);

  const filtered = projects.filter((p) => p.name.toLowerCase().includes(search.toLowerCase()));

  const closeMenu = () => { setMenu(null); setConfirm(null); };

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
        {["Plan Type", "Date"].map((f) => (
          <button key={f} className="flex items-center gap-1.5 h-9 px-3 border border-border rounded-lg text-[11px] font-mono text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
            {f}<ChevronDown size={11} />
          </button>
        ))}
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
              <div
                key={p.id}
                /*
                 * `border-beam` sets `isolation: isolate`, so the dropdown
                 * below is sealed inside THIS card's stacking context and no
                 * z-index on it can reach past a later sibling card. Raising
                 * the whole card while its menu is open is what lets the menu
                 * cover the card underneath.
                 */
                className={`relative border border-border rounded-xl bg-card hover:bg-accent/40 hover-lift animate-stagger border-beam transition-colors p-6 flex flex-col min-h-[160px] ${
                  menu === p.id ? "z-30" : ""
                }`}
                style={{ animationDelay: `${i * 50}ms` }}
              >
                <div className="border-beam-content flex flex-col flex-1">
                  <div className="w-10 h-10 border border-border rounded-lg flex items-center justify-center text-foreground mb-4">
                    <Icon size={16} />
                  </div>

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

                  <div className="flex items-center justify-between mt-4">
                    <span className="text-[11px] font-mono text-muted-foreground">
                      {new Date(p.created_at).toLocaleDateString()}
                    </span>
                    <button
                      onClick={() => {
                        setConfirm(null);
                        setMenu(menu === p.id ? null : p.id);
                      }}
                      aria-label={`Actions for ${p.name}`}
                      className="text-muted-foreground hover:text-foreground press-scale"
                    >
                      <MoreVertical size={13} />
                    </button>
                  </div>
                </div>

                {menu === p.id && (
                  <div className="absolute top-full mt-1 right-4 w-44 bg-popover border border-border rounded-lg overflow-hidden z-20 shadow-lg animate-pop-in origin-top-right">
                    {confirm === p.id ? (
                      <>
                        <p className="px-4 pt-3 pb-2 text-[10px] font-mono text-muted-foreground leading-relaxed">
                          Remove permanently? The estimate goes with it.
                        </p>
                        <button
                          onClick={() => handleRemove(p.id)}
                          className="w-full text-left px-4 py-2.5 text-[11px] font-mono text-red-400 hover:bg-red-950/40 border-t border-border transition-colors"
                        >
                          Yes, remove it
                        </button>
                        <button
                          onClick={() => setConfirm(null)}
                          className="w-full text-left px-4 py-2.5 text-[11px] font-mono text-foreground hover:bg-accent border-t border-border transition-colors"
                        >
                          Cancel
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => setConfirm(p.id)}
                          className="w-full text-left px-4 py-2.5 text-[11px] font-mono text-foreground hover:bg-accent border-b border-border transition-colors"
                        >
                          Remove project
                        </button>
                        <button
                          onClick={closeMenu}
                          className="w-full text-left px-4 py-2.5 text-[11px] font-mono text-foreground hover:bg-accent transition-colors"
                        >
                          Close
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

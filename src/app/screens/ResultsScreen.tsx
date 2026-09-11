import { useEffect, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router";
import {
  ArrowLeft,
  MessageSquare,
  HelpCircle,
  Download,
  Wallet,
  Box,
  ListChecks,
  CheckCircle2,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import { Btn, Mono } from "../components/ui";
import { getProject, type Project } from "../../lib/projects";
import { confidenceLabel, type ExtractionReport, type PricedLine } from "../../lib/estimate";

const peso = (n: number) =>
  `₱${n.toLocaleString("en-PH", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

type NavState = { projectId?: string };

function StatCard({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="border border-border rounded-lg p-6 bg-card hover-lift animate-stagger">
      <div className="flex items-center justify-between mb-3">
        <Mono className="text-[10px]">{label}</Mono>
        <span className="w-8 h-8 rounded-full border border-border flex items-center justify-center text-muted-foreground shrink-0">
          {icon}
        </span>
      </div>
      <p className="text-[26px] font-mono font-bold text-foreground leading-none">{value}</p>
    </div>
  );
}

function ReadQuality({ extraction }: { extraction: ExtractionReport }) {
  const label = confidenceLabel(extraction.confidence);
  const tone =
    label === "High"
      ? "border-emerald-800 text-emerald-400 bg-emerald-950/30"
      : label === "Medium"
      ? "border-amber-800 text-amber-400 bg-amber-950/30"
      : "border-red-800 text-red-400 bg-red-950/30";

  const chainsOk = extraction.chains.filter((c) => c.ok).length;
  const hasFrame = extraction.concrete_volume_m3 != null;

  return (
    <div className="mb-8 animate-stagger">
      <div className="border border-border rounded-lg bg-card overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <Mono>How this plan was read</Mono>
          <span className={`h-6 px-3 rounded-full text-[10px] font-mono tracking-widest uppercase flex items-center border ${tone}`}>
            {label} confidence &middot; {Math.round(extraction.confidence * 100)}%
          </span>
        </div>

        <div
          className={`grid grid-cols-2 divide-x divide-border ${
            hasFrame ? "sm:grid-cols-3 lg:grid-cols-5" : "sm:grid-cols-4"
          }`}
        >
          <div className="px-5 py-4">
            <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1.5">Envelope</p>
            <p className="text-[12px] font-mono text-foreground">
              {extraction.envelope_w_m.toFixed(2)} &times; {extraction.envelope_l_m.toFixed(2)} m
            </p>
            <p className="text-[10px] font-mono text-muted-foreground/70">read as {extraction.unit}</p>
          </div>
          <div className="px-5 py-4">
            <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1.5">Wall length</p>
            <p className="text-[12px] font-mono text-foreground">{extraction.total_wall_m.toFixed(2)} m</p>
            <p className="text-[10px] font-mono text-muted-foreground/70">
              {extraction.exterior_wall_m.toFixed(1)} ext + {extraction.interior_wall_m.toFixed(1)} int
            </p>
          </div>
          <div className="px-5 py-4">
            <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1.5">Dimension chains</p>
            <p className="text-[12px] font-mono text-foreground">{chainsOk}/{extraction.chains.length} closed</p>
            <p className="text-[10px] font-mono text-muted-foreground/70">{extraction.rooms.length} rooms read</p>
          </div>
          <div className="px-5 py-4">
            <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1.5">Area accounted</p>
            <p className="text-[12px] font-mono text-foreground">{Math.round(extraction.area_accounted_ratio * 100)}%</p>
            <p className="text-[10px] font-mono text-muted-foreground/70">
              {extraction.doors} doors &middot; {extraction.windows} windows
            </p>
          </div>
          {hasFrame && (
            <div className="px-5 py-4">
              <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1.5">Concrete</p>
              <p className="text-[12px] font-mono text-foreground">
                {extraction.concrete_volume_m3!.toFixed(2)} m&sup3;
              </p>
              <p className="text-[10px] font-mono text-amber-500/80">
                {extraction.column_count} columns &middot; assumed
              </p>
            </div>
          )}
        </div>
      </div>

      {extraction.warnings.length > 0 && (
        <div className="border border-orange-900/50 rounded-lg p-5 bg-orange-950/10 mt-4">
          <Mono className="block mb-3 text-orange-400">
            {extraction.warnings.length} thing{extraction.warnings.length > 1 ? "s" : ""} to check
          </Mono>
          <ul className="space-y-2">
            {extraction.warnings.map((w, i) => (
              <li key={i} className="text-[11px] font-mono text-muted-foreground leading-relaxed flex gap-2">
                <span className="text-orange-400/70 shrink-0">&bull;</span>
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function ResultsScreen() {
  const navigate = useNavigate();
  const location = useLocation();
  const { projectId } = (location.state ?? {}) as NavState;

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState("");

  useEffect(() => {
    if (!projectId) {
      setError("No project selected.");
      setLoading(false);
      return;
    }
    getProject(projectId)
      .then((p) => {
        if (!p) setError("Project not found.");
        setProject(p);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load project."))
      .finally(() => setLoading(false));
  }, [projectId]);

  const rows = project?.line_items ?? [];
  const grandTotal = project?.grand_total ?? 0;
  const estimatedItems = rows.reduce((sum, r) => sum + r.quantity, 0);
  const materialTypesCount = rows.length;

  // Summing `quantity` across lines is only meaningful when every line is a
  // count. An OCR estimate mixes pieces, bags, cubic metres and kilograms
  // into one number, so show the wall length it was all derived from instead.
  const thirdTile = project?.extraction
    ? { label: "Wall Length", value: `${project.extraction.total_wall_m.toFixed(2)} m` }
    : { label: "Estimated Items", value: estimatedItems.toLocaleString() };

  const breakdown = [...rows]
    .map((r) => {
      // CHB01 and CHB02 are both named "Concrete Hollow Blocks" - only `unit`
      // separates 4in from 6in. Deformed bars, THHN wire and breakers collide
      // the same way. So the size belongs in the label, and the key must be
      // the SKU: two siblings sharing a React key can be mismatched on
      // re-render, and here that would animate the wrong bar.
      const size = r.unit && r.unit.includes("/") ? r.unit.split("/")[0].trim() : null;
      return {
        id: r.item_id,
        label: size ? `${r.item_name} (${size})` : r.item_name,
        total: r.line_total,
        pct: grandTotal ? (r.line_total / grandTotal) * 100 : 0,
      };
    })
    .sort((a, b) => b.total - a.total)
    .slice(0, 8);

  const exportCSV = () => {
    if (!project) return;
    const header = "Item ID,Material,Unit,Unit Price,Quantity,Line Total\n";
    const body = rows
      .map((r) => `${r.item_id},${r.item_name},${r.unit ?? ""},${peso(r.unit_price)},${r.quantity},${peso(r.line_total)}`)
      .join("\n");
    const blob = new Blob([header + body], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `trace_${project.name}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-background animate-page-in">
      {/* Header — standalone, no sidebar */}
      <header className="h-[70px] flex items-center justify-between px-8 border-b border-border shrink-0">
        <div className="flex items-center gap-4">
          <span className="font-mono font-light text-foreground" style={{ letterSpacing: "12px", fontSize: "16px" }}>
            TRACE
          </span>
          <div className="w-px h-4 bg-border" />
          <button
            onClick={() => navigate("/projects")}
            className="flex items-center gap-2 text-[11px] font-mono tracking-[0.14em] uppercase text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft size={12} />
            Projects <span className="text-foreground/70">/ {project?.name ?? "…"}</span>
          </button>
        </div>
        <div className="flex items-center gap-2">
          <Btn variant="ghost" onClick={() => navigate("/feedback")} icon={<MessageSquare size={12} />}>
            Feedback
          </Btn>
          <button
            onClick={() => navigate("/help")}
            className="w-8 h-8 flex items-center justify-center rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-accent press-scale"
          >
            <HelpCircle size={14} />
          </button>
        </div>
      </header>

      <div className="p-10 max-w-6xl mx-auto">
        {loading && (
          <p className="text-[12px] font-mono text-muted-foreground flex items-center gap-2">
            <Loader2 size={12} className="animate-spin-slow" /> Loading project…
          </p>
        )}

        {!loading && error && (
          <div className="border border-red-900/50 rounded-lg p-6 bg-red-950/20 flex items-start gap-3">
            <AlertTriangle size={16} className="text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-[12px] font-mono text-red-400 mb-1">{error}</p>
              <button onClick={() => navigate("/projects")} className="text-[11px] font-mono text-muted-foreground hover:text-foreground underline-grow">
                Back to Projects
              </button>
            </div>
          </div>
        )}

        {!loading && project && project.status === "processing" && (
          <div className="border border-border rounded-lg p-6 bg-card flex items-center gap-3">
            <Loader2 size={14} className="animate-spin-slow text-muted-foreground" />
            <p className="text-[12px] font-mono text-muted-foreground">This project is still scanning — check back shortly.</p>
          </div>
        )}

        {!loading && project && project.status === "error" && (
          <div className="border border-red-900/50 rounded-lg p-6 bg-red-950/20 flex items-start gap-3">
            <AlertTriangle size={16} className="text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-[12px] font-mono text-red-400 mb-1">Scan failed</p>
              <p className="text-[11px] font-mono text-muted-foreground">{project.error_message}</p>
            </div>
          </div>
        )}

        {!loading && project && project.status === "completed" && (
          <>
            {/* Title row */}
            <div className="flex items-start justify-between mb-6">
              <div>
                <h1 className="text-[30px] font-semibold text-foreground leading-tight mb-1">{project.name}</h1>
                <p className="text-[13px] font-mono text-muted-foreground mb-3">{project.description || "No description"}</p>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="px-2.5 py-1 border border-border rounded-md text-[10px] font-mono uppercase tracking-[0.08em] text-foreground">
                    {project.plan_type}
                  </span>
                  <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-[0.08em]">
                    Scanned {new Date(project.updated_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              <Btn variant="secondary" onClick={exportCSV} icon={<Download size={11} />}>Export CSV</Btn>
            </div>

            {/* Stat cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
              <StatCard icon={<Wallet size={15} />} label="Total Estimated Cost" value={peso(grandTotal)} />
              <StatCard icon={<Box size={15} />} label="Material Types" value={String(materialTypesCount)} />
              <StatCard icon={<ListChecks size={15} />} label={thirdTile.label} value={thirdTile.value} />
            </div>

            {project.extraction && <ReadQuality extraction={project.extraction} />}

            {rows.length === 0 && (
              <div className="border border-border rounded-lg p-6 bg-card mb-8">
                <p className="text-[12px] font-mono text-muted-foreground">
                  No materials were matched for this scan. Symbol matching compares your plan against
                  reference images you upload, so it finds nothing until at least one is added — open the
                  Symbol Library and add a clean crop of each symbol you want counted.
                </p>
              </div>
            )}

            {rows.length > 0 && (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-8">
                <div className="border border-border rounded-lg overflow-hidden bg-card animate-stagger">
                  <div className="px-5 py-3.5 border-b border-border"><Mono>Material Estimate</Mono></div>
                  <div className="grid grid-cols-5 px-5 py-3 bg-card border-b border-border">
                    <Mono>Material</Mono>
                    <Mono>SKU</Mono>
                    <Mono>Quantity</Mono>
                    <Mono>Unit Cost</Mono>
                    <Mono>Total Cost</Mono>
                  </div>
                  {rows.map((r, i) => (
                    <div key={i} className="grid grid-cols-5 items-center px-5 py-3 border-b border-border last:border-0 hover:bg-accent/30 transition-colors">
                      <div className="min-w-0 pr-2">
                        <p className="text-[12px] font-mono text-foreground truncate">{r.item_name}</p>
                        {(r as PricedLine).derivation && (
                          <p
                            className="text-[9px] font-mono text-muted-foreground/60 truncate"
                            title={(r as PricedLine).derivation}
                          >
                            {(r as PricedLine).derivation}
                          </p>
                        )}
                      </div>
                      <span className="text-[12px] font-mono text-muted-foreground">{r.item_id}</span>
                      <span className="text-[12px] font-mono text-muted-foreground">{r.quantity}{r.unit ? ` (${r.unit})` : ""}</span>
                      <span className="text-[12px] font-mono text-muted-foreground">{peso(r.unit_price)}</span>
                      <span className="text-[12px] font-mono text-foreground">{peso(r.line_total)}</span>
                    </div>
                  ))}
                  <div className="flex items-center justify-between px-5 py-4 bg-accent/20">
                    <Mono>Total Estimated Cost</Mono>
                    <span className="text-[15px] font-mono font-bold text-foreground">{peso(grandTotal)}</span>
                  </div>
                </div>

                <div className="border border-border rounded-lg p-6 bg-card animate-stagger">
                  <Mono className="block mb-5">Cost Breakdown</Mono>
                  <div className="space-y-3.5">
                    {breakdown.map((b) => (
                      <div key={b.id} className="flex items-center gap-3">
                        <span className="text-[11px] font-mono text-foreground w-36 truncate shrink-0" title={b.label}>{b.label}</span>
                        <div className="flex-1 h-2 rounded-full bg-accent overflow-hidden">
                          <div className="h-full bg-foreground/70 rounded-full transition-all duration-700" style={{ width: `${Math.max(2, b.pct)}%` }} />
                        </div>
                        <span className="text-[10px] font-mono text-muted-foreground w-10 text-right shrink-0">{b.pct.toFixed(1)}%</span>
                        <span className="text-[11px] font-mono text-foreground w-16 text-right shrink-0">{peso(b.total)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {project.unmatched_detections && project.unmatched_detections.length > 0 && (
              <div className="border border-orange-900/50 rounded-lg p-6 bg-orange-950/10 mb-8">
                <Mono className="block mb-3 text-orange-400">
                  {project.unmatched_detections.length} Unmatched Detection{project.unmatched_detections.length > 1 ? "s" : ""}
                </Mono>
                <p className="text-[11px] font-mono text-muted-foreground mb-3">
                  Symbols the model found but couldn't confidently map to a catalog SKU — review manually.
                </p>
                <div className="flex flex-wrap gap-2">
                  {project.unmatched_detections.map((d, i) => (
                    <span key={i} className="px-2.5 py-1 border border-border rounded-md text-[10px] font-mono text-muted-foreground">
                      {d.label} ({Math.round(d.confidence * 100)}%)
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="border border-border rounded-lg p-6 bg-card animate-stagger">
              <Mono className="block mb-5">Analysis Status</Mono>
              <div className="flex items-start gap-3">
                <span className="w-5 h-5 rounded-full bg-emerald-500/15 border border-emerald-500/40 flex items-center justify-center text-emerald-400 shrink-0 mt-0.5">
                  <CheckCircle2 size={12} />
                </span>
                <div>
                  <p className="text-[11px] font-mono text-foreground">Scan complete</p>
                  <p className="text-[10px] font-mono text-muted-foreground/70">
                    Created {new Date(project.created_at).toLocaleString()} · Updated {new Date(project.updated_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

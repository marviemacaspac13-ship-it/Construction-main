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
import { getProject, hasEditableInputs, type Project } from "../../lib/projects";
import type { PricedLine } from "../../lib/estimate";
import { PlanViewer } from "../components/PlanViewer";
import { EstimateEditor, editorButton } from "../components/EstimateEditor";
import { ManualEstimateEditor } from "../components/ManualEstimateEditor";
import { csvEstimate } from "../../lib/editor-input";

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

  const [dirty, setDirty] = useState(false);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  const leave = (path: string) => { if (!dirty || window.confirm("Leave without saving your corrections?")) navigate(path); };
  const reload = async () => {
    const next = await getProject(projectId!);
    if (!next) throw new Error("Could not reopen the saved project. Retry saving to recover the saved revision.");
    setProject(next); setDirty(false);
  };
  const replacePlan = () => {
    if (!project || !window.confirm("Replace or rescan this plan? The current saved version is retained. Previous corrections will not be carried forward; review the new result before editing it.")) return;
    if (dirty && !window.confirm("Discard the unsaved corrections in this tab?")) return;
    navigate("/upload", { state: { projectId: project.id, expectedRevision: project.active_revision_id ?? null,
      draft: { name: project.name, description: project.description ?? "", planType: project.plan_type,
        wallHeightM: project.saved_scan?.original_input.params.default_wall_height_m } } });
  };
  const rows = project?.line_items ?? [];
  const grandTotal = project?.grand_total ?? 0;
  const materialTypesCount = rows.length;
  const savedWallHeight = project?.plan_type === "Floor Plan"
    ? project.active_revision?.effective_input.params.default_wall_height_m
    : undefined;

  // Summing `quantity` across lines is only meaningful when every line is a
  // count. An OCR estimate mixes pieces, bags, cubic metres and kilograms
  // into one number, so show the wall length it was all derived from instead.
  const savedPlan = project?.active_revision?.effective_input.plan;
  const electricalAllowances=savedPlan?.electrical_review?.estimate_scope==='reviewed_device_allowances';
  const partialElectrical=savedPlan?.electrical_review?.estimate_scope==='devices_and_boxes'||electricalAllowances;
  const scopeExclusions=project?.active_revision?.estimate.scope_exclusions??[];
  const excludedElectricalDevices=savedPlan?.electrical_review?.choices.filter(c=>c.disposition==='exclude').length??0;
  const excludedElectricalBoxes=savedPlan?.electrical_review?.choices.filter(c=>c.disposition==='include'&&!c.box_item_id).length??0;
  const wallLength = savedPlan?.walls.reduce((sum, wall) => sum + wall.length_m, 0)
    ?? project?.extraction?.total_wall_m;
  const thirdTile = wallLength !== undefined && project?.plan_type === "Floor Plan"
    ? { label: "Wall Length", value: `${wallLength.toFixed(2)} m` }
    : { label: "Plan Type", value: project?.plan_type.replace(" Plan", "") ?? "—" };

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
    const scopeRows=partialElectrical ? [['Estimate scope',electricalAllowances?'Reviewed electrical devices, compatible boxes, and light/outlet wire and conduit allowances':'Partial: electrical devices and compatible boxes only'],...(electricalAllowances?[['Quantity basis','Wire and conduit are estimating allowances, not measured circuit routes.']]:[]),...scopeExclusions.map(t=>['Excluded',t])].map(row=>row.map(s=>`"${s.replace(/"/g,'""')}"`).join(',')).join('\r\n')+'\r\n\r\n' : '';
    const blob = new Blob([scopeRows+csvEstimate(rows)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `trace_${project.name}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-background animate-page-in">
      {/* Header — standalone, no sidebar */}
      <header className="min-h-[70px] flex flex-wrap gap-3 items-center justify-between px-4 sm:px-8 py-3 border-b border-border shrink-0">
        <div className="flex items-center gap-4">
          <span className="font-mono font-light text-foreground" style={{ letterSpacing: "12px", fontSize: "16px" }}>
            TRACE
          </span>
          <div className="w-px h-4 bg-border" />
          <button
            onClick={() => leave("/projects")}
            className="flex items-center gap-2 text-[11px] font-mono tracking-[0.14em] uppercase text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft size={12} />
            Projects <span className="text-foreground/70 max-w-40 sm:max-w-md truncate">/ {project?.name ?? "…"}</span>
          </button>
        </div>
        <div className="flex items-center gap-2">
          <Btn variant="ghost" onClick={() => leave("/feedback")} icon={<MessageSquare size={12} />}>
            Feedback
          </Btn>
          <button
            onClick={() => leave("/help")}
            className="w-8 h-8 flex items-center justify-center rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-accent press-scale"
          >
            <HelpCircle size={14} />
          </button>
        </div>
      </header>

      <div className="p-4 sm:p-10 max-w-[1600px] mx-auto">
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
              <button onClick={() => leave("/projects")} className="text-[11px] font-mono text-muted-foreground hover:text-foreground underline-grow">
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
          <div className="space-y-6">
          <div className="border border-red-900/50 rounded-lg p-6 bg-red-950/20 flex items-start gap-3">
            <AlertTriangle size={16} className="text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-[12px] font-mono text-red-400 mb-1">Scan failed</p>
              <p className="text-[11px] font-mono text-muted-foreground">{project.error_message}</p>
            </div>
          </div>
          <button className={editorButton} onClick={replacePlan}>Upload another plan</button>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
            <ManualEstimateEditor key={project.id} project={project} onSaved={reload} onDirty={setDirty}/>
            <PlanViewer key={project.plan_asset?.id ?? project.id} projectId={project.id} asset={project.plan_asset}/>
          </div>
          </div>
        )}

        {!loading && project && project.status === "completed" && (
          <>
            {/* Title row */}
            <div className="flex flex-wrap gap-4 items-start justify-between mb-6">
              <div>
                <h1 className="text-[30px] font-semibold text-foreground leading-tight mb-1">{project.name}</h1>
                <p className="text-[13px] font-mono text-muted-foreground mb-3">{project.description || "No description"}</p>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="px-2.5 py-1 border border-border rounded-md text-[10px] font-mono uppercase tracking-[0.08em] text-foreground">
                    {project.plan_type}
                  </span>
                  <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-[0.08em]">
                    Saved {new Date(project.updated_at).toLocaleDateString()}
                  </span>
                </div>
                {partialElectrical&&<section className="mt-4 text-sm" aria-label="Partial electrical estimate scope">
                  <h2 className="font-medium">{electricalAllowances?'Electrical estimate with light and outlet allowances':'Partial estimate: electrical devices and boxes'}</h2>
                  {electricalAllowances&&<p className="mt-2 text-muted-foreground">Wire and conduit quantities for supported lights and convenience outlets use estimating allowances, not measured circuit routes.</p>}
                  <p className="mt-2 text-muted-foreground">{scopeExclusions[0]}</p>
                  {scopeExclusions.length>1&&<details className="mt-2"><summary className="min-h-11 py-3 cursor-pointer">{excludedElectricalDevices} device{excludedElectricalDevices===1?'':'s'} and {excludedElectricalBoxes} box{excludedElectricalBoxes===1?'':'es'} excluded — view reasons</summary><ul className="list-disc pl-5 text-muted-foreground break-words">{scopeExclusions.slice(1).map((t,i)=><li key={i}>{t}</li>)}</ul></details>}
                  <p className="mt-2 text-muted-foreground">To change reviewed device counts or box selections, replace / rescan the plan. Project prices can be edited below.</p>
                </section>}
                {savedWallHeight !== undefined && (
                  <p className="mt-3 text-sm text-muted-foreground">
                    Wall height: {savedWallHeight.toFixed(2)} m · All walls
                  </p>
                )}
              </div>
              <div className="flex flex-wrap gap-2"><button className={editorButton} onClick={replacePlan}>Replace / rescan plan</button><Btn variant="secondary" onClick={exportCSV} icon={<Download size={11} />}>Export CSV</Btn></div>
            </div>

            {/* Stat cards */}
            {!hasEditableInputs(project) && (
              <p className="text-sm text-muted-foreground mb-6 max-w-2xl">
                This saved estimate does not include the original calculation inputs.
                Re-upload and rescan the plan before making quantity or price corrections.
              </p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
              <StatCard icon={<Wallet size={15} />} label={partialElectrical?'Partial Estimated Cost':'Total Estimated Cost'} value={peso(grandTotal)} />
              <StatCard icon={<Box size={15} />} label="Material Types" value={String(materialTypesCount)} />
              <StatCard icon={<ListChecks size={15} />} label={thirdTile.label} value={thirdTile.value} />
            </div>

            <button
              onClick={() => leave("/projects")}
              className="flex items-center gap-2 text-[11px] font-mono tracking-[0.14em] uppercase text-muted-foreground hover:text-foreground transition-colors mb-8 press-scale"
            >
              <ArrowLeft size={12} />
              Back to Projects
            </button>

            {hasEditableInputs(project) && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start mb-8">
                <EstimateEditor key={project.active_revision!.id} project={project} onSaved={reload} onDirty={setDirty}/>
                <div className="min-w-0 lg:sticky lg:top-4"><PlanViewer key={project.plan_asset?.id ?? project.id} projectId={project.id} asset={project.plan_asset} scanRevisionId={project.active_revision?.scan_revision_id} fixtureReview={project.saved_scan?.original_input.plan.fixture_review} electricalReview={project.saved_scan?.original_input.plan.electrical_review}/></div>
              </div>
            )}
            {rows.length === 0 && (
              <>
              {!hasEditableInputs(project) && <PlanViewer key={project.plan_asset?.id ?? project.id} projectId={project.id} asset={project.plan_asset} scanRevisionId={project.active_revision?.scan_revision_id}/>}
              <div className="border border-border rounded-lg p-6 bg-card mb-8">
                <p className="text-[12px] font-mono text-muted-foreground">
                  This saved estimate has no priced material lines. Review the entered quantities and original plan before using the result.
                </p>
              </div>
              </>
            )}

            {rows.length > 0 && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8 items-start">
                <div className="min-w-0 border border-border rounded-lg overflow-hidden bg-card animate-stagger">
                  <div className="px-5 py-3.5 border-b border-border"><Mono>Material Estimate</Mono></div>
                  <p className="sm:hidden px-5 py-2 text-sm text-muted-foreground">Scroll horizontally to view all material columns.</p>
                  <div role="region" aria-label="Material estimate table" tabIndex={0} className="overflow-x-auto focus-visible:outline-2 focus-visible:outline-foreground">
                  <div className="min-w-[680px]">
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
                        <p className="text-[12px] font-mono text-foreground truncate" title={r.item_name}>{r.item_name}</p>
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
                      <span className="min-w-0 pr-3 text-[12px] font-mono text-muted-foreground">
                        <span className="block">{r.quantity}</span>
                        {r.unit && <span className="block text-[11px] whitespace-normal break-words">{r.unit}</span>}
                      </span>
                      <span className="text-[12px] font-mono text-muted-foreground">{peso(r.unit_price)}</span>
                      <span className="text-[12px] font-mono text-foreground">{peso(r.line_total)}</span>
                    </div>
                  ))}
                  <div className="flex items-center justify-between px-5 py-4 bg-accent/20">
                    <Mono>{partialElectrical?'Partial Estimated Cost':'Total Estimated Cost'}</Mono>
                    <span className="text-[15px] font-mono font-bold text-foreground">{peso(grandTotal)}</span>
                  </div>
                  </div></div>
                </div>

                <div className="min-w-0 space-y-6 lg:sticky lg:top-4">
                {!hasEditableInputs(project) && <PlanViewer key={project.plan_asset?.id ?? project.id} projectId={project.id} asset={project.plan_asset} scanRevisionId={project.active_revision?.scan_revision_id}/>}
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
                  <p className="text-[11px] font-mono text-foreground">{project.saved_scan?.scan.method === "manual" ? "Manual estimate saved" : "Estimate saved"}</p>
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

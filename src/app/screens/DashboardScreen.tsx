import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router";
import {
  FolderOpen,
  Files,
  Wallet,
  Upload,
  Clock,
  ArrowUpRight,
  Building2,
  Zap,
  Droplets,
  Loader2,
} from "lucide-react";
import { SectionBar, Mono } from "../components/ui";
import { NewProjectModal } from "../components/NewProjectModal";
import { listProjects, type Project } from "../../lib/projects";

const formatCurrency = (n: number) =>
  `₱${n.toLocaleString("en-PH", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

const relativeTime = (iso: string) => {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
};

const PLAN_ICONS: Record<string, ReactNode> = {
  Structural: <Building2 size={14} />,
  "Floor Plan": <Building2 size={14} />,
  Electrical: <Zap size={14} />,
  "Electrical Plan": <Zap size={14} />,
  Plumbing: <Droplets size={14} />,
  "Plumbing Plan": <Droplets size={14} />,
};

function IconBox({ children }: { children: ReactNode }) {
  return (
    <span className="w-9 h-9 rounded-lg border border-border bg-accent flex items-center justify-center text-foreground shrink-0">
      {children}
    </span>
  );
}

function StatCard({ icon, label, value, sub, delay }: { icon: ReactNode; label: string; value: string; sub: string; delay: number }) {
  return (
    <div className="border border-border rounded-lg p-6 bg-card hover-lift animate-stagger" style={{ animationDelay: `${delay}ms` }}>
      <div className="flex items-center gap-3 mb-4">
        <IconBox>{icon}</IconBox>
        <Mono className="text-[10px]">{label}</Mono>
      </div>
      <p className="text-[28px] font-mono font-bold text-foreground leading-none mb-2">{value}</p>
      <p className="text-[10px] font-mono text-muted-foreground">{sub}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: Project["status"] }) {
  const label = status === "completed" ? "Completed" : status === "processing" ? "Processing" : "Error";
  const completed = status === "completed";
  return (
    <span className="inline-flex items-center gap-1.5 text-[10px] font-mono tracking-[0.1em] uppercase text-muted-foreground">
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${completed ? "bg-foreground" : status === "processing" ? "bg-muted-foreground animate-pulse" : "bg-red-500"}`} />
      <span className={completed ? "text-foreground" : status === "error" ? "text-red-400" : "text-muted-foreground"}>{label}</span>
    </span>
  );
}

function CostBar({ label, project, value, max }: { label: string; project: string; value: number; max: number }) {
  const pct = Math.max(4, Math.round((value / max) * 100));
  return (
    <div className="flex items-center gap-3">
      <IconBox>{PLAN_ICONS[label] ?? <Building2 size={14} />}</IconBox>
      <div className="flex-1">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[11px] font-mono text-foreground">
            {label} <span className="text-muted-foreground">· {project}</span>
          </span>
          <span className="text-[11px] font-mono text-foreground">{formatCurrency(value)}</span>
        </div>
        <div className="h-1.5 rounded-full bg-accent overflow-hidden">
          <div className="h-full bg-foreground/70 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
        </div>
      </div>
    </div>
  );
}

function AverageCostRow({ type, value }: { type: string; value: number }) {
  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-border last:border-0">
      <IconBox>{PLAN_ICONS[type] ?? <Building2 size={14} />}</IconBox>
      <div className="flex-1 min-w-0">
        <p className="text-[11px] font-mono uppercase tracking-[0.08em] text-foreground truncate">{type}</p>
        <p className="text-[9px] font-mono text-muted-foreground uppercase tracking-[0.1em]">Average per plan</p>
      </div>
      <span className="text-[13px] font-mono font-bold text-foreground shrink-0">{formatCurrency(value)}</span>
    </div>
  );
}

export function DashboardScreen() {
  const navigate = useNavigate();
  const [modalOpen, setModalOpen] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listProjects().then(setProjects).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const completed = useMemo(() => projects.filter((p) => p.status === "completed" && p.grand_total != null), [projects]);

  const totalEstimatedCost = useMemo(() => completed.reduce((sum, p) => sum + (p.grand_total ?? 0), 0), [completed]);

  const planTypeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    projects.forEach((p) => { counts[p.plan_type] = (counts[p.plan_type] ?? 0) + 1; });
    return counts;
  }, [projects]);

  const planBreakdown = Object.entries(planTypeCounts).map(([type, n]) => `${n} ${type.replace(" Plan", "")}`).join(" · ") || "No plans yet";

  const highestCostByPlanType = useMemo(() => {
    const best: Record<string, Project> = {};
    completed.forEach((p) => {
      const current = best[p.plan_type];
      if (!current || (p.grand_total ?? 0) > (current.grand_total ?? 0)) best[p.plan_type] = p;
    });
    return Object.entries(best).map(([label, p]) => ({ label, project: p.name, value: p.grand_total ?? 0 }));
  }, [completed]);

  const averageCostByPlanType = useMemo(() => {
    const groups: Record<string, number[]> = {};
    completed.forEach((p) => { (groups[p.plan_type] ??= []).push(p.grand_total ?? 0); });
    return Object.entries(groups).map(([type, values]) => ({
      type,
      value: values.reduce((a, b) => a + b, 0) / values.length,
    }));
  }, [completed]);

  const maxCost = Math.max(1, ...highestCostByPlanType.map((c) => c.value));

  const recentProjects = projects.slice(0, 5);
  const recentActivity = projects
    .slice()
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 6)
    .map((p) => ({
      text: p.status === "completed" ? "Estimate completed" : p.status === "error" ? "Scan failed" : "Scan started",
      project: p.name,
      time: relativeTime(p.updated_at),
    }));

  return (
    <>
      <div className="p-10 w-full animate-page-in">
        <SectionBar>Dashboard</SectionBar>

        {loading ? (
          <p className="text-[12px] font-mono text-muted-foreground flex items-center gap-2 mb-8">
            <Loader2 size={12} className="animate-spin-slow" /> Loading dashboard…
          </p>
        ) : (
          <>
            {/* Top statistics */}
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 mb-8">
              <StatCard icon={<FolderOpen size={15} />} label="Total Projects" value={String(projects.length)} sub="All time" delay={0} />
              <StatCard icon={<Files size={15} />} label="Total Plans" value={String(projects.length)} sub={planBreakdown} delay={70} />
              <StatCard icon={<Wallet size={15} />} label="Total Estimated Cost" value={formatCurrency(totalEstimatedCost)} sub={`Across ${completed.length} completed estimate${completed.length === 1 ? "" : "s"}`} delay={140} />
            </div>

            {/* Recent Projects + Quick Actions */}
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-8">
              <div className="xl:col-span-2 animate-stagger" style={{ animationDelay: "210ms" }}>
                <div className="flex items-center justify-between mb-4">
                  <Mono className="text-[11px]">Recent Projects</Mono>
                  <button onClick={() => navigate("/projects")} className="flex items-center gap-1 text-[10px] font-mono tracking-[0.14em] uppercase text-muted-foreground hover:text-foreground transition-colors">
                    View all <ArrowUpRight size={11} />
                  </button>
                </div>
                <div className="border border-border rounded-lg overflow-hidden">
                  <div className="grid grid-cols-5 px-5 py-3 bg-card border-b border-border">
                    <Mono>Project</Mono><Mono>Plan Type</Mono><Mono>Status</Mono><Mono>Estimate</Mono><Mono>Date</Mono>
                  </div>
                  {recentProjects.length === 0 && (
                    <div className="px-5 py-10 text-center">
                      <p className="text-[12px] font-mono text-muted-foreground">No projects yet — create one to get started.</p>
                    </div>
                  )}
                  {recentProjects.map((p, i) => (
                    <div key={p.id} className="grid grid-cols-5 items-center px-5 py-3.5 border-b border-border last:border-0 hover:bg-accent/30 transition-colors animate-stagger" style={{ animationDelay: `${260 + i * 50}ms` }}>
                      <span className="text-[12px] font-mono text-foreground">{p.name}</span>
                      <span className="text-[12px] font-mono text-muted-foreground">{p.plan_type.replace(" Plan", "")}</span>
                      <StatusBadge status={p.status} />
                      <span className="text-[12px] font-mono text-foreground">{p.grand_total != null ? formatCurrency(p.grand_total) : "—"}</span>
                      <span className="text-[12px] font-mono text-muted-foreground">{new Date(p.created_at).toLocaleDateString()}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="animate-stagger" style={{ animationDelay: "260ms" }}>
                <Mono className="text-[11px] block mb-4">Quick Actions</Mono>
                <div className="space-y-2">
                  <button onClick={() => setModalOpen(true)} className="w-full flex items-center gap-3 border border-border rounded-lg px-4 py-3 hover:bg-accent press-scale text-left transition-colors">
                    <Upload size={14} className="text-muted-foreground shrink-0" />
                    <div className="min-w-0">
                      <p className="text-[11px] font-mono tracking-[0.1em] uppercase text-foreground">Upload Plan</p>
                      <p className="text-[10px] font-mono text-muted-foreground">Compute new estimate</p>
                    </div>
                  </button>
                  <button onClick={() => navigate("/history")} className="w-full flex items-center gap-3 border border-border rounded-lg px-4 py-3 hover:bg-accent press-scale text-left transition-colors">
                    <Clock size={14} className="text-muted-foreground shrink-0" />
                    <div className="min-w-0">
                      <p className="text-[11px] font-mono tracking-[0.1em] uppercase text-foreground">View History</p>
                      <p className="text-[10px] font-mono text-muted-foreground">Past estimates</p>
                    </div>
                  </button>
                </div>
              </div>
            </div>

            {/* Cost Analytics */}
            <SectionBar>Cost Analytics</SectionBar>
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-8">
              <div className="xl:col-span-2 border border-border rounded-lg p-6 bg-card animate-stagger" style={{ animationDelay: "310ms" }}>
                <Mono className="text-[11px] block mb-5">Highest Estimated Cost by Plan Type</Mono>
                {highestCostByPlanType.length === 0 ? (
                  <p className="text-[11px] font-mono text-muted-foreground">No completed estimates yet.</p>
                ) : (
                  <div className="space-y-5">
                    {highestCostByPlanType.map((c) => <CostBar key={c.label} label={c.label} project={c.project} value={c.value} max={maxCost} />)}
                  </div>
                )}
              </div>

              <div className="border border-border rounded-lg p-6 bg-card animate-stagger" style={{ animationDelay: "360ms" }}>
                <Mono className="text-[11px] block mb-3">Average Estimated Cost</Mono>
                {averageCostByPlanType.length === 0 ? (
                  <p className="text-[11px] font-mono text-muted-foreground">No completed estimates yet.</p>
                ) : (
                  <div>{averageCostByPlanType.map((a) => <AverageCostRow key={a.type} type={a.type} value={a.value} />)}</div>
                )}
              </div>
            </div>

            {/* Recent Activity */}
            <div className="animate-stagger" style={{ animationDelay: "410ms" }}>
              <Mono className="text-[11px] block mb-4">Recent Activity</Mono>
              <div className="border border-border rounded-lg overflow-hidden">
                {recentActivity.length === 0 && (
                  <div className="px-5 py-6 text-center"><p className="text-[12px] font-mono text-muted-foreground">Nothing yet.</p></div>
                )}
                {recentActivity.map((a, i) => (
                  <div key={i} className="flex items-center justify-between px-5 py-3 border-b border-border last:border-0">
                    <span className="text-[11px] font-mono text-muted-foreground">
                      {a.text} <span className="text-foreground/70">— {a.project}</span>
                    </span>
                    <span className="text-[10px] font-mono text-muted-foreground/60">{a.time}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      <NewProjectModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </>
  );
}

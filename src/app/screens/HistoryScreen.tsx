import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import {
  Search,
  ChevronDown,
  ClipboardList,
  CalendarDays,
  Wallet,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Check,
  X,
} from "lucide-react";
import { listProjects, type Project } from "../../lib/projects";
import { SectionBar, Mono } from "../components/ui";

const PAGE_SIZE = 8;
const peso = (n: number) => `₱${n.toLocaleString("en-PH")}`;

const PLAN_TYPE_OPTIONS = ["All", "Floor Plan", "Electrical Plan", "Plumbing Plan"];
const STATUS_OPTIONS: { label: string; value: "All" | Project["status"] }[] = [
  { label: "All",        value: "All" },
  { label: "Completed",  value: "completed" },
  { label: "Processing", value: "processing" },
  { label: "Error",      value: "error" },
];
const DATE_OPTIONS = ["All Time", "Today", "This Week", "This Month"] as const;
type DateFilter = (typeof DATE_OPTIONS)[number];

function isWithinDateFilter(iso: string, filter: DateFilter): boolean {
  if (filter === "All Time") return true;
  const d = new Date(iso);
  const now = new Date();
  if (filter === "Today") {
    return d.toDateString() === now.toDateString();
  }
  if (filter === "This Week") {
    const startOfWeek = new Date(now);
    startOfWeek.setDate(now.getDate() - now.getDay());
    startOfWeek.setHours(0, 0, 0, 0);
    return d >= startOfWeek;
  }
  // This Month
  return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
}

function StatCard({ icon, label, value, sub, delay }: { icon: ReactNode; label: string; value: string; sub: string; delay: number }) {
  return (
    <div className="border border-border rounded-lg p-6 bg-card hover-lift animate-stagger" style={{ animationDelay: `${delay}ms` }}>
      <div className="flex items-center justify-between mb-4">
        <Mono className="text-[10px]">{label}</Mono>
        <span className="w-8 h-8 rounded-full border border-border flex items-center justify-center text-muted-foreground shrink-0">{icon}</span>
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

function FilterDropdown<T extends string>({
  label,
  options,
  value,
  onChange,
  isOpen,
  onToggle,
  getLabel = (v) => v,
}: {
  label: string;
  options: T[];
  value: T;
  onChange: (v: T) => void;
  isOpen: boolean;
  onToggle: () => void;
  getLabel?: (v: T) => string;
}) {
  const active = value !== ("All" as T);
  return (
    <div className="relative">
      <button
        onClick={onToggle}
        className={`flex items-center gap-1.5 h-10 px-4 border rounded-lg text-[11px] font-mono transition-colors press-scale ${
          active ? "border-foreground/40 text-foreground bg-accent" : "border-border text-muted-foreground hover:text-foreground hover:bg-accent"
        }`}
      >
        {active ? getLabel(value) : label}
        {active ? (
          <span
            role="button"
            tabIndex={-1}
            onClick={(e) => { e.stopPropagation(); onChange("All" as T); }}
            className="text-muted-foreground hover:text-foreground"
          >
            <X size={11} />
          </span>
        ) : (
          <ChevronDown size={11} className={`transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} />
        )}
      </button>
      {isOpen && (
        <div className="absolute right-0 top-11 w-44 bg-popover border border-border rounded-lg overflow-hidden z-[100] shadow-lg animate-pop-in origin-top-right">
          {options.map((opt) => (
            <button
              key={opt}
              onClick={() => { onChange(opt); onToggle(); }}
              className={`w-full flex items-center justify-between gap-2 px-3.5 py-2.5 text-[11px] font-mono text-left transition-colors border-b border-border last:border-0 ${
                opt === value ? "text-foreground bg-accent" : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
              }`}
            >
              {getLabel(opt)}
              {opt === value && <Check size={11} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function HistoryScreen() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  const [planTypeFilter, setPlanTypeFilter] = useState("All");
  const [statusFilter, setStatusFilter] = useState<"All" | Project["status"]>("All");
  const [dateFilter, setDateFilter] = useState<DateFilter>("All Time");
  const [openDropdown, setOpenDropdown] = useState<"planType" | "date" | "status" | null>(null);
  const filterBarRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listProjects().then(setProjects).catch(() => {}).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (filterBarRef.current && !filterBarRef.current.contains(e.target as Node)) setOpenDropdown(null);
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return projects.filter((p) => {
      if (q && !p.name.toLowerCase().includes(q) && !p.plan_type.toLowerCase().includes(q)) return false;
      if (planTypeFilter !== "All" && p.plan_type !== planTypeFilter) return false;
      if (statusFilter !== "All" && p.status !== statusFilter) return false;
      if (!isWithinDateFilter(p.created_at, dateFilter)) return false;
      return true;
    });
  }, [projects, search, planTypeFilter, statusFilter, dateFilter]);

  const now = new Date();
  const thisMonthCount = useMemo(
    () => projects.filter((p) => {
      const d = new Date(p.created_at);
      return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
    }).length,
    [projects]
  );
  const currentMonthLabel = now.toLocaleDateString("en-US", { month: "long", year: "numeric" });

  const totalEstimatedCost = useMemo(
    () => projects.filter((p) => p.status === "completed").reduce((sum, p) => sum + (p.grand_total ?? 0), 0),
    [projects]
  );

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * PAGE_SIZE;
  const pageRows = filtered.slice(start, start + PAGE_SIZE);

  const updateSearch = (v: string) => {
    setSearch(v);
    setPage(1);
  };

  const setPlanType = (v: string) => { setPlanTypeFilter(v); setPage(1); };
  const setStatus = (v: "All" | Project["status"]) => { setStatusFilter(v); setPage(1); };
  const setDate = (v: DateFilter) => { setDateFilter(v); setPage(1); };

  const hasActiveFilters = planTypeFilter !== "All" || statusFilter !== "All" || dateFilter !== "All Time";
  const clearFilters = () => { setPlanTypeFilter("All"); setStatusFilter("All"); setDateFilter("All Time"); setPage(1); };

  return (
    <div className="h-full flex flex-col p-10 animate-page-in">
      <SectionBar>Estimation History</SectionBar>

      {loading ? (
        <p className="text-[12px] font-mono text-muted-foreground flex items-center gap-2 mb-8">
          <Loader2 size={12} className="animate-spin-slow" /> Loading history…
        </p>
      ) : (
        <div className="flex-1 min-h-0 flex flex-col">
          {/* Top statistics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 mb-6 shrink-0">
            <StatCard icon={<ClipboardList size={15} />} label="Total Estimates" value={String(projects.length)} sub="All time" delay={0} />
            <StatCard icon={<CalendarDays size={15} />} label="This Month" value={String(thisMonthCount).padStart(2, "0")} sub={currentMonthLabel} delay={70} />
            <StatCard icon={<Wallet size={15} />} label="Total Estimated Cost" value={peso(totalEstimatedCost)} sub="Across all completed estimates" delay={140} />
          </div>

          {/* Search + filters */}
          <div
  className="relative z-50 flex items-center justify-between gap-3 mb-4 flex-wrap shrink-0 animate-stagger"
  style={{ animationDelay: "190ms" }}
>
            <div className="flex items-center h-10 border border-border rounded-lg px-3 gap-2 w-72 focus-within:border-foreground/25 transition-colors">
              <Search size={13} className="text-muted-foreground shrink-0" />
              <input
                value={search}
                onChange={(e) => updateSearch(e.target.value)}
                placeholder="Search project or ID..."
                className="bg-transparent text-[12px] font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none flex-1"
              />
            </div>
            <div ref={filterBarRef} className="relative z-50 flex items-center gap-2">
              {hasActiveFilters && (
                <button
                  onClick={clearFilters}
                  className="flex items-center gap-1.5 h-10 px-3 text-[11px] font-mono text-muted-foreground hover:text-foreground transition-colors"
                >
                  Clear filters <X size={11} />
                </button>
              )}
              <FilterDropdown
                label="Plan Type"
                options={PLAN_TYPE_OPTIONS}
                value={planTypeFilter}
                onChange={setPlanType}
                isOpen={openDropdown === "planType"}
                onToggle={() => setOpenDropdown((d) => (d === "planType" ? null : "planType"))}
                getLabel={(v) => v.replace(" Plan", "")}
              />
              <FilterDropdown
                label="Date"
                options={[...DATE_OPTIONS]}
                value={dateFilter}
                onChange={setDate}
                isOpen={openDropdown === "date"}
                onToggle={() => setOpenDropdown((d) => (d === "date" ? null : "date"))}
              />
              <FilterDropdown
                label="Status"
                options={STATUS_OPTIONS.map((o) => o.value)}
                value={statusFilter}
                onChange={setStatus}
                isOpen={openDropdown === "status"}
                onToggle={() => setOpenDropdown((d) => (d === "status" ? null : "status"))}
                getLabel={(v) => STATUS_OPTIONS.find((o) => o.value === v)?.label ?? v}
              />
            </div>
          </div>

          {/* Table */}
          <div
  className="relative z-0 flex-1 min-h-0 border border-border rounded-lg overflow-hidden flex flex-col animate-stagger"
  style={{ animationDelay: "240ms" }}
>
            <div className="grid grid-cols-6 px-5 py-3 bg-card border-b border-border shrink-0">
              <Mono>Project</Mono><Mono>Plan Type</Mono><Mono>Estimate</Mono><Mono>Status</Mono><Mono>Date</Mono><Mono>Action</Mono>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto" style={{ scrollbarWidth: "none" }}>
              {pageRows.length === 0 && (
                <div className="px-5 py-10 text-center">
                  <p className="text-[12px] font-mono text-muted-foreground">
                    {projects.length === 0
                      ? "No estimates yet — create a project to get started."
                      : "No estimates match your search or filters."}
                  </p>
                </div>
              )}

              {pageRows.map((p, i) => (
                <div key={p.id} className="grid grid-cols-6 items-center px-5 py-3.5 border-b border-border last:border-0 hover:bg-accent/30 transition-colors animate-stagger" style={{ animationDelay: `${280 + i * 40}ms` }}>
                  <span className="text-[12px] font-mono text-foreground">{p.name}</span>
                  <span className="text-[12px] font-mono text-muted-foreground">{p.plan_type}</span>
                  <span className="text-[12px] font-mono text-foreground">{p.grand_total != null ? peso(p.grand_total) : "—"}</span>
                  <StatusBadge status={p.status} />
                  <div className="flex items-center gap-3">
                    <span className="text-[12px] font-mono text-foreground">{new Date(p.created_at).toLocaleDateString()}</span>
                    <span className="text-[11px] font-mono text-muted-foreground/60">{new Date(p.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                  <button
                    onClick={() => navigate("/results", { state: { projectId: p.id } })}
                    disabled={p.status !== "completed"}
                    className="flex items-center gap-1.5 text-[11px] font-mono tracking-[0.08em] uppercase text-foreground hover:text-muted-foreground press-scale w-fit disabled:opacity-30 disabled:pointer-events-none"
                  >
                    View Result <ArrowRight size={11} />
                  </button>
                </div>
              ))}
            </div>

            {/* Pagination footer */}
            <div className="flex items-center justify-between px-5 py-3.5 bg-background/40 border-t border-border shrink-0">
              <p className="text-[11px] font-mono text-muted-foreground">
                Showing {filtered.length === 0 ? 0 : start + 1} to {Math.min(start + PAGE_SIZE, filtered.length)} of {filtered.length} results
              </p>
              <div className="flex items-center gap-1">
                <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={safePage === 1} className="flex items-center gap-1 h-8 px-3 rounded-lg text-[11px] font-mono uppercase tracking-[0.08em] text-muted-foreground hover:text-foreground hover:bg-accent disabled:opacity-30 disabled:pointer-events-none transition-colors">
                  <ChevronLeft size={11} /> Prev
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((n) => (
                  <button key={n} onClick={() => setPage(n)} className={`w-8 h-8 rounded-lg text-[11px] font-mono transition-colors ${n === safePage ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground hover:bg-accent"}`}>
                    {n}
                  </button>
                ))}
                <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={safePage === totalPages} className="flex items-center gap-1 h-8 px-3 rounded-lg text-[11px] font-mono uppercase tracking-[0.08em] text-muted-foreground hover:text-foreground hover:bg-accent disabled:opacity-30 disabled:pointer-events-none transition-colors">
                  Next <ChevronRight size={11} />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
export type ProjectStatus = "Completed" | "Processing";

export const recentProjects = [
  { id: "STR1",  name: "STR1",  type: "Floor Plan",      date: "11 Jun 2026", status: "Completed"  as ProjectStatus, estimate: 2_400_000 },
  { id: "ELCT1", name: "ELCT1", type: "Electrical Plan", date: "12 Jun 2026", status: "Completed"  as ProjectStatus, estimate: 580_000   },
  { id: "PLM81", name: "PLM81", type: "Plumbing Plan",   date: "07 Jun 2026", status: "Completed"  as ProjectStatus, estimate: 320_000   },
  { id: "PLM87", name: "PLM87", type: "Plumbing Plan",   date: "07 Jun 2026", status: "Processing" as ProjectStatus, estimate: null      },
];

export const allProjects = [
  { id: "STR1",  name: "STR1",  type: "Floor Plan",     date: "11-06-2026" },
  { id: "ELCT1", name: "ELCT1", type: "Electrical Plan", date: "12-06-2026" },
  { id: "PLM81", name: "PLM81", type: "Plumbing Plan",   date: "07-06-2026" },
  { id: "STR2",  name: "STR2",  type: "Floor Plan",     date: "05-06-2026" },
  { id: "PLM82", name: "PLM82", type: "Plumbing Plan",   date: "03-06-2026" },
  { id: "ELCT2", name: "ELCT2", type: "Electrical Plan", date: "01-06-2026" },
];

export const historyItems = [
  { action: "Exported Result", project: "STR1",  type: "Floor Plan",     time: "9:30 AM",  date: "15-06-2026" },
  { action: "Created Project", project: "STR1",  type: "Floor Plan",     time: "9:00 AM",  date: "15-06-2026" },
  { action: "Removed Project", project: "ELCT1", type: "Electrical Plan", time: "7:00 AM",  date: "15-06-2026" },
  { action: "Exported Result", project: "PLM81", type: "Plumbing Plan",   time: "3:15 PM",  date: "14-06-2026" },
  { action: "Created Project", project: "PLM81", type: "Plumbing Plan",   time: "2:45 PM",  date: "14-06-2026" },
  { action: "Created Project", project: "STR2",  type: "Floor Plan",     time: "11:00 AM", date: "12-06-2026" },
];

/** Top-of-dashboard stat cards. */
export const dashboardStats = {
  totalProjects: 14,
  totalProjectsSub: "All time",
  totalPlans: 12,
  planBreakdown: "6 Floor · 4 Electrical · 2 Plumbing",
  totalEstimatedCost: 12_400_000,
  totalEstimatedCostSub: "Across completed estimates",
};

/** Highest single estimate recorded per plan type. */
export const highestCostByPlanType = [
  { label: "Structural", project: "STR1",  value: 2_400_000 },
  { label: "Electrical", project: "ELCT1", value: 580_000   },
  { label: "Plumbing",   project: "PLM81", value: 320_000   },
];

/** Aggregate cost breakdown across all completed estimates. */
export const costSummary = {
  structural: 7_200_000,
  electrical: 2_100_000,
  plumbing: 1_300_000,
  total: 10_600_000,
  highestEstimate: 2_400_000,
  averageEstimate: 883_000,
  totalEstimates: 12,
};

export const recentActivity = [
  { text: "Estimate generated",         project: "STR1",  time: "11 Jun 2026 · 14:32" },
  { text: "Electrical plan analyzed",   project: "ELCT1", time: "12 Jun 2026 · 09:17" },
  { text: "Plumbing estimate completed", project: "PLM81", time: "07 Jun 2026 · 16:45" },
  { text: "Plan uploaded",              project: "PLM87", time: "07 Jun 2026 · 16:42" },
];

/** ₱2,400,000 -> "₱2.40M", ₱580,000 -> "₱580K", null -> "—" */
export function formatCurrency(value: number | null): string {
  if (value === null) return "—";
  if (value >= 1_000_000) return `₱${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `₱${Math.round(value / 1000)}K`;
  return `₱${value}`;
}

/** Average estimate per plan type across all completed plans of that type. */
export const averageCostByPlanType = [
  { type: "Floor Plan",      value: 1_820_000 },
  { type: "Electrical Plan", value: 465_000   },
  { type: "Plumbing Plan",   value: 298_000   },
];

export type EstimationStatus = "Completed" | "Processing";

export const estimationHistory: {
  project: string;
  type: string;
  estimate: number;
  status: EstimationStatus;
  date: string;
  time: string;
}[] = [
  { project: "STR1",  type: "Floor Plan",      estimate: 104_668, status: "Completed", date: "15 Jun 2026", time: "09:30 AM" },
  { project: "ELCT1", type: "Electrical Plan", estimate: 42_850,  status: "Completed", date: "15 Jun 2026", time: "09:15 AM" },
  { project: "PLM81", type: "Plumbing Plan",   estimate: 28_420,  status: "Completed", date: "14 Jun 2026", time: "03:15 PM" },
  { project: "PLM87", type: "Plumbing Plan",   estimate: 35_620,  status: "Completed", date: "14 Jun 2026", time: "02:45 PM" },
  { project: "STR2",  type: "Floor Plan",      estimate: 185_300, status: "Completed", date: "12 Jun 2026", time: "11:00 AM" },
  { project: "ELCT2", type: "Electrical Plan", estimate: 31_180,  status: "Completed", date: "11 Jun 2026", time: "10:20 AM" },
  { project: "PLM70", type: "Plumbing Plan",   estimate: 19_950,  status: "Completed", date: "10 Jun 2026", time: "04:40 PM" },
  { project: "STR0",  type: "Floor Plan",      estimate: 96_240,  status: "Completed", date: "08 Jun 2026", time: "01:30 PM" },
  { project: "ELCT3", type: "Electrical Plan", estimate: 54_200,  status: "Completed", date: "28 May 2026", time: "09:00 AM" },
  { project: "PLM65", type: "Plumbing Plan",   estimate: 22_780,  status: "Completed", date: "25 May 2026", time: "02:10 PM" },
  { project: "STR3",  type: "Floor Plan",      estimate: 142_900, status: "Completed", date: "20 May 2026", time: "10:45 AM" },
  { project: "ELCT4", type: "Electrical Plan", estimate: 38_760,  status: "Completed", date: "15 May 2026", time: "03:30 PM" },
];
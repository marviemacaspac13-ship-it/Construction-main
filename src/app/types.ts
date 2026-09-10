export const ROUTES = [
  { path: "/sign-in",          label: "01 Sign In" },
  { path: "/sign-up",          label: "02 Sign Up" },
  { path: "/dashboard",        label: "03 Dashboard" },
  { path: "/projects",         label: "04 Projects" },
  { path: "/projects/details", label: "05 Project Details" },
  { path: "/upload",           label: "06 Upload Plan" },
  { path: "/scanning",         label: "07 Scanning" },
  { path: "/results",          label: "08 Results" },
  { path: "/history",          label: "09 History" },
  { path: "/train-model",      label: "10 Train Model" },
  { path: "/feedback",         label: "11 Feedback" },
  { path: "/help",             label: "12 Help" },
  { path: "/profile",          label: "13 Profile" },
  { path: "/menu",             label: "14 Menu" },
] as const;

export type RoutePath = (typeof ROUTES)[number]["path"];
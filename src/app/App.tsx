import { Routes, Route, Navigate, Outlet } from "react-router";
import { AppShell } from "./components/AppShell";
import { SignInScreen } from "./screens/SignInScreen";
import { SignUpScreen } from "./screens/SignUpScreen";
import { DashboardScreen } from "./screens/DashboardScreen";
import { ProjectsScreen } from "./screens/ProjectsScreen";
import { ProjectDetailsScreen } from "./screens/ProjectDetailsScreen";
import { UploadScreen } from "./screens/UploadScreen";
import { ScanningScreen } from "./screens/ScanningScreen";
import { ResultsScreen } from "./screens/ResultsScreen";
import { HistoryScreen } from "./screens/HistoryScreen";
import { FeedbackScreen } from "./screens/FeedbackScreen";
import { HelpScreen } from "./screens/HelpScreen";
import { ProfileScreen } from "./screens/ProfileScreen";
import { MenuDropdownScreen } from "./screens/MenuDropdownScreen";
import { TrainModelScreen } from "./screens/TrainModelScreen";
import { SymbolLibraryScreen } from "./screens/SymbolLibraryScreen";

function AppLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/sign-in" replace />} />

      <Route path="/sign-in" element={<SignInScreen />} />
      <Route path="/sign-up" element={<SignUpScreen />} />

      <Route path="/results" element={<ResultsScreen />} />

      <Route element={<AppLayout />}>
        <Route path="/dashboard" element={<DashboardScreen />} />
        <Route path="/projects" element={<ProjectsScreen />} />
        <Route path="/projects/details" element={<ProjectDetailsScreen />} />
        <Route path="/upload" element={<UploadScreen />} />
        <Route path="/scanning" element={<ScanningScreen />} />
        <Route path="/history" element={<HistoryScreen />} />
        <Route path="/symbol-library" element={<SymbolLibraryScreen />} />
        <Route path="/train-model" element={<TrainModelScreen />} />
        <Route path="/feedback" element={<FeedbackScreen />} />
        <Route path="/help" element={<HelpScreen />} />
        <Route path="/profile" element={<ProfileScreen />} />
        <Route path="/menu" element={<MenuDropdownScreen />} />
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

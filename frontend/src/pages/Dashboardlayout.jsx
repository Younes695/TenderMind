import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import DashboardHeader from "../components/DashboardHeader";
import DashboardSidebar from "../components/DashboardSidebare";

function Dashboardlayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { pathname } = useLocation();

  const isGoNoGo = pathname.startsWith("/go-no-go");
  const isTenderWorkspace = pathname.startsWith("/tenders/");

  const headerTitle = isGoNoGo
    ? "Go / No-Go — RUH-2026-184"
    : isTenderWorkspace
      ? "RUH-2026-184"
      : "Dashboard";

  const headerSubtitle = isGoNoGo
    ? "AI recommendation with evidence · human decision required"
    : isTenderWorkspace
      ? "Riyadh Smart Infrastructure · Tender Workspace"
      : undefined;

  return (
    <div className="flex h-screen overflow-hidden bg-[#f8f7f3]">

      {/* Sidebar */}
      <DashboardSidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Right Side */}
      <div className="flex min-w-0 flex-1 flex-col">

        {/* Header — same component, title only changes per page */}
        <DashboardHeader
          onMenuClick={() => setSidebarOpen(true)}
          title={headerTitle}
          subtitle={headerSubtitle}
        />

        {/* Page Content */}
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>

      </div>
    </div>
  );
}

export default Dashboardlayout;

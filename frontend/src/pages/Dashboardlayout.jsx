import { useState } from "react";
import { Outlet, useLocation, useParams } from "react-router-dom";
import DashboardHeader from "../components/DashboardHeader";
import DashboardSidebar from "../components/DashboardSidebare";

function Dashboardlayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { pathname } = useLocation();
  const params = useParams();

  const isGoNoGo = pathname.startsWith("/go-no-go");
  const isTenderWorkspace = pathname.startsWith("/tenders/");
  const tenderId = params.tender_id || params.tenderId || null;

  const SECTION_TITLES = {
    "/tenders": "Tenders",
    "/company-knowledge": "Company Knowledge",
    "/work-packages": "Work Packages",
    "/qa": "Q&A",
    "/approvals": "Approvals",
    "/documents": "Documents",
    "/subcontractors": "Subcontractors",
    "/analytics": "Analytics",
    "/notifications": "Notifications",
    "/help": "Help",
    "/settings": "Settings",
  };

  const headerTitle = isGoNoGo
    ? tenderId ? `Go / No-Go — ${tenderId}` : "Go / No-Go"
    : isTenderWorkspace && tenderId
      ? tenderId
      : SECTION_TITLES[pathname] || "Dashboard";

  const headerSubtitle = isGoNoGo
    ? "AI recommendation with evidence · human decision required"
    : isTenderWorkspace
      ? tenderId ? `${tenderId} · Tender Workspace` : undefined
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

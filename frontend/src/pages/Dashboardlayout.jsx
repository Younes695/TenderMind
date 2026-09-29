import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import apiClient from "../api/client";
import DashboardHeader from "../components/DashboardHeader";
import DashboardSidebar from "../components/DashboardSidebare";
import Assistant from "../components/Assistant";
import { useT } from "../i18n";

function Dashboardlayout() {
  const t = useT();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [openReviews, setOpenReviews] = useState(0);
  const { pathname } = useLocation();
  const navigate = useNavigate();

  // Bell badge: open review items across the account's tenders (Stage 5H).
  useEffect(() => {
    let alive = true;
    const load = () => apiClient.getNotifications()
      .then((d) => { if (alive) setOpenReviews(d?.count || 0); })
      .catch(() => {});
    load();
    const interval = setInterval(load, 60000);
    window.addEventListener("tm:notifications-changed", load);
    return () => { alive = false; clearInterval(interval); window.removeEventListener("tm:notifications-changed", load); };
  }, [pathname]);
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
    "/news": "Tender Radar",
    "/materials": "Materials & prices",
    "/help": "Help",
    "/settings": "Settings",
  };

  const headerTitle = isGoNoGo
    ? tenderId ? `${t("Go / No-Go")} - ${tenderId}` : t("Go / No-Go")
    : isTenderWorkspace && tenderId
      ? tenderId
      : t(SECTION_TITLES[pathname] || "Dashboard");

  const headerSubtitle = isGoNoGo
    ? t("AI recommendation with evidence · human decision required")
    : isTenderWorkspace
      ? tenderId ? `${tenderId} · ${t("Tender Workspace")}` : undefined
      : undefined;

  return (
    <div className="flex h-screen overflow-hidden bg-[#f8f7f3]">

      {/* Sidebar */}
      <DashboardSidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Right Side */}
      <div className="flex min-w-0 flex-1 flex-col">

        {/* Header - same component, title only changes per page */}
        <DashboardHeader
          onMenuClick={() => setSidebarOpen(true)}
          title={headerTitle}
          subtitle={headerSubtitle}
          hasNotifications={openReviews > 0}
          notificationCount={openReviews}
          onNotificationsClick={() => navigate("/notifications")}
        />

        {/* Page Content */}
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
          <Assistant />
        </main>

      </div>
    </div>
  );
}

export default Dashboardlayout;

import { Link, NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  FolderOpen,
  Scale,
  Network,
  MessageSquare,
  Stamp,
  FileText,
  Truck,
  Database,
  BarChart3,
  Bell,
  LifeBuoy,
  Settings,
  X,
} from "lucide-react";

import logo from "../assets/logo.jpg";


// ================= Main Navigation =================

const mainNav = [
  {
    to: "/dashboard",
    label: "Dashboard",
    icon: LayoutDashboard,
    end: true,
  },
  {
    to: "/tenders",
    label: "Tenders",
    icon: FolderOpen,
  },
  {
    to: "/go-no-go",
    label: "Go / No-Go",
    icon: Scale,
  },
  {
    to: "/work-packages",
    label: "Work Packages",
    icon: Network,
  },
  {
    to: "/qa",
    label: "Q&A",
    icon: MessageSquare,
  },
  {
    to: "/approvals",
    label: "Approvals",
    icon: Stamp,
    badge: 4,
  },
  {
    to: "/documents",
    label: "Documents",
    icon: FileText,
  },
  {
    to: "/subcontractors",
    label: "Subcontractors",
    icon: Truck,
  },
  {
    to: "/company-knowledge",
    label: "Company Knowledge",
    icon: Database,
  },
  {
    to: "/analytics",
    label: "Analytics",
    icon: BarChart3,
  },
];


// ================= Bottom Navigation =================

const bottomNav = [
  {
    to: "/notifications",
    label: "Notifications",
    icon: Bell,
  },
  {
    to: "/help",
    label: "Help",
    icon: LifeBuoy,
  },
  {
    to: "/settings",
    label: "Settings",
    icon: Settings,
  },
];


// ================= Navigation Item =================

function NavItem({
  to,
  label,
  icon: Icon,
  badge,
  end,
  onNavigate,
}) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      className={({ isActive }) =>
        `flex h-[46px] items-center gap-3 rounded-xl px-3 text-[15px] font-medium transition-colors ${
          isActive
            ? "bg-white font-semibold text-[#162A4C]"
            : "text-[#c5d0e6] hover:bg-white/5 hover:text-white"
        }`
      }
    >
      <Icon
        size={20}
        strokeWidth={1.8}
        className="shrink-0"
      />

      <span className="min-w-0 flex-1 truncate">
        {label}
      </span>

      {badge ? (
        <span className="flex h-6 min-w-6 items-center justify-center rounded-full bg-[#C8A96B] px-2 text-[12px] font-bold text-[#162A4C]">
          {badge}
        </span>
      ) : null}
    </NavLink>
  );
}


// ================= Sidebar Content (logo kept as-is) =================

function SidebarContent({ user, onNavigate, onClose }) {
  const initials = user.name
    .split(" ")
    .map((word) => word[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="flex h-full flex-col bg-[#0F1D38] px-4 py-5 text-white">
      {/* ================= Logo — unchanged ================= */}

      <div className="mb-7 flex items-center justify-between px-2">
        <Link
          to="/"
          onClick={onNavigate}
          className="flex items-center gap-3"
        >
          <img
            src={logo}
            alt="TenderMind logo"
            className="h-10 w-10 rounded-lg object-cover"
          />

          <span className="text-[20px] font-black tracking-wide">
            TENDER
            <span className="text-[#C8A96B]">
              MIND
            </span>
          </span>
        </Link>

        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="flex h-10 w-10 items-center justify-center rounded-lg text-[#c5d0e6] hover:bg-white/10 hover:text-white lg:hidden"
          >
            <X size={20} />
          </button>
        )}
      </div>


      {/* ================= Main Navigation ================= */}

      <nav
        className="sidebar-scroll space-y-1 overflow-y-auto pr-1"
        aria-label="Main"
      >
        {mainNav.map((item) => (
          <NavItem
            key={item.to}
            {...item}
            onNavigate={onNavigate}
          />
        ))}
      </nav>


      {/* ================= Spacer ================= */}

      <div className="flex-1" />


      {/* ================= Bottom Navigation ================= */}

      <nav
        className="space-y-1 border-t border-white/10 pt-4"
        aria-label="Secondary"
      >
        {bottomNav.map((item) => (
          <NavItem
            key={item.to}
            {...item}
            onNavigate={onNavigate}
          />
        ))}
      </nav>


      {/* ================= User Card ================= */}

      <div className="mt-4 flex items-center gap-3 rounded-xl bg-white/5 px-3 py-3">

        {/* Avatar */}

        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#C8A96B] text-[14px] font-bold text-[#162A4C]">
          {initials}
        </span>


        {/* User Info */}

        <div className="min-w-0">

          <p className="truncate text-[15px] font-bold text-white">
            {user.name}
          </p>

          <p className="truncate text-[13px] text-[#a9b8d4]">
            {user.role}
          </p>

        </div>

      </div>
    </div>
  );
}


// ================= Sidebar =================

function DashboardSidebar({
  user = {
    name: "Khalid Alotaibi",
    role: "Tender Manager",
  },
  open = false,
  onClose,
}) {
  const handleNavigate = () => {
    onClose?.();
  };

  return (
    <>
      {/* Desktop */}
      <aside className="hidden h-screen w-[280px] shrink-0 lg:block">
        <SidebarContent user={user} onNavigate={undefined} onClose={undefined} />
      </aside>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={onClose}
          />
          <aside className="absolute left-0 top-0 h-full w-[300px] max-w-[85vw] shadow-2xl">
            <SidebarContent user={user} onNavigate={handleNavigate} onClose={onClose} />
          </aside>
        </div>
      )}
    </>
  );
}

export default DashboardSidebar;

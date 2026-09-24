import { useState } from "react";
import { Link } from "react-router-dom";
import { Search, Bell, Menu } from "lucide-react";

function DashboardHeader({
  title = "Dashboard",
  subtitle,
  activeTenders = 5,
  newTenderTo = "/tenders/new",
  hasNotifications = false,
  onSearch,
  onNotificationsClick,
  onMenuClick,
}) {
  const [query, setQuery] = useState("");

  // "Tuesday pipeline · 5 active tenders" — اليوم بيتحسب أوتوماتيك
  const weekday = new Date().toLocaleDateString("en-US", { weekday: "long" });

  const handleChange = (e) => {
    setQuery(e.target.value);
    onSearch?.(e.target.value);
  };

  return (
    <header className="flex w-full items-center gap-3 border-b border-[#ebe8e1] bg-white px-4 py-4 sm:px-6 lg:px-8 lg:py-5">
      {/* Mobile menu button */}
      <button
        type="button"
        onClick={onMenuClick}
        aria-label="Open menu"
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[#e2e6ee] bg-white text-[#162A4C] transition-colors hover:bg-[#f5f6f9] lg:hidden"
      >
        <Menu size={20} strokeWidth={1.8} />
      </button>

      {/* Title */}
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[22px] font-bold leading-tight tracking-tight text-[#162A4C] sm:text-[24px]">
          {title}
        </h1>
        <p className="mt-0.5 truncate text-[14px] text-[#4b5f86] sm:text-[15px]">
          {subtitle ?? `${weekday} pipeline · ${activeTenders} active tenders`}
        </p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 sm:gap-3">
        <div className="relative hidden md:block md:w-[220px] lg:w-[260px]">
          <Search
            size={18}
            strokeWidth={1.8}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#6b7a99]"
          />
          <input
            type="search"
            value={query}
            onChange={handleChange}
            placeholder="Search tenders..."
            aria-label="Search tenders"
            className="h-11 w-full rounded-xl border border-[#e2e6ee] bg-white pl-10 pr-3 text-[15px] text-[#162A4C] placeholder:text-[#9aa5bd] outline-none transition focus:border-[#162A4C] focus:ring-2 focus:ring-[#162A4C]/15"
          />
        </div>

        <Link
          to={newTenderTo}
          className="hidden h-11 items-center rounded-xl bg-[#162A4C] px-5 text-[15px] font-bold whitespace-nowrap text-white transition-colors hover:bg-[#0F1D38] focus:outline-none focus:ring-2 focus:ring-[#162A4C]/40 focus:ring-offset-2 sm:flex"
        >
          + New Tender
        </Link>

        {/* Mobile: icon only */}
        <Link
          to={newTenderTo}
          aria-label="New Tender"
          className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#162A4C] text-[20px] font-bold text-white sm:hidden"
        >
          +
        </Link>

        <button
          type="button"
          onClick={onNotificationsClick}
          aria-label="Notifications"
          className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[#e2e6ee] bg-white text-[#162A4C] transition-colors hover:bg-[#f5f6f9]"
        >
          <Bell size={19} strokeWidth={1.8} />
          {hasNotifications && (
            <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-[#C8A96B] ring-2 ring-white" />
          )}
        </button>
      </div>

      {/* Mobile search row */}
      <div className="relative mt-1 basis-full md:hidden">
        <Search
          size={18}
          strokeWidth={1.8}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#6b7a99]"
        />
        <input
          type="search"
          value={query}
          onChange={handleChange}
          placeholder="Search tenders..."
          aria-label="Search tenders"
          className="h-11 w-full rounded-xl border border-[#e2e6ee] bg-white pl-10 pr-3 text-[15px] text-[#162A4C] placeholder:text-[#9aa5bd] outline-none transition focus:border-[#162A4C] focus:ring-2 focus:ring-[#162A4C]/15"
        />
      </div>
    </header>
  );
}

export default DashboardHeader;

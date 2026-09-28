import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { FolderOpen, Plus, Search, ChevronRight } from "lucide-react";
import apiClient from "../api/client";
import { useT } from "../i18n";

function TendersList() {
  const t = useT();
  const [tenders, setTenders] = useState(null);
  const [error, setError] = useState(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    apiClient.listTenders().then((t) => setTenders(Array.isArray(t) ? t : [])).catch((e) => setError(e.message || "Failed to load tenders"));
  }, []);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const list = tenders || [];
    const filtered = needle
      ? list.filter((t) => `${t.id} ${t.title || ""} ${t.client || ""} ${t.location || ""}`.toLowerCase().includes(needle))
      : list;
    return [...filtered].sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
  }, [tenders, q]);

  return (
    <div className="mx-auto max-w-[1100px] p-4 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-[22px] font-black text-[#101828]"><FolderOpen size={22} /> {t("Tenders")}</h1>
          <p className="text-[14px] text-[#667085]">{t("Every tender in your workspace. Open one to see requirements, evidence and the bid decision.")}</p>
        </div>
        <Link to="/tenders/new" className="flex h-[44px] items-center justify-center gap-2 rounded-xl bg-[#162A4C] px-5 text-[14px] font-bold text-white hover:bg-[#0F1D38]">
          <Plus size={18} /> {t("New Tender")}
        </Link>
      </div>

      <div className="mt-5 flex items-center gap-2 rounded-xl border border-[#e8e4dc] bg-white px-3">
        <Search size={18} className="text-[#98a2b3]" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("Search by ID, title, client or location")} className="h-[44px] w-full bg-transparent text-[14px] outline-none" />
      </div>

      {error && <div className="mt-4 rounded-xl border border-[#f5c6c6] bg-[#fdf0f0] p-3 text-[14px] text-[#a33a3a]">{error}</div>}
      {!tenders && !error && <p className="mt-6 text-[14px] text-[#667085]">{t("Loading tenders...")}</p>}
      {tenders && shown.length === 0 && (
        <div className="mt-6 rounded-2xl border border-[#e8e4dc] bg-white p-8 text-center text-[14px] text-[#667085]">
          {q ? t("No tenders match your search.") : t("No tenders yet — create your first tender.")}
        </div>
      )}

      <div className="mt-4 space-y-2">
        {shown.map((t) => (
          <Link key={t.id} to={`/tenders/${encodeURIComponent(t.id)}`} data-testid="tender-row"
            className="flex items-center gap-4 rounded-2xl border border-[#e8e4dc] bg-white p-4 transition-colors hover:border-[#162A4C]">
            <div className="min-w-0 flex-1">
              <p className="truncate text-[15px] font-bold text-[#101828]">{t.title || t.id}</p>
              <p className="mt-0.5 truncate text-[13px] text-[#667085]">
                {t.id}{t.client ? ` • ${t.client}` : ""}{t.location ? ` • ${t.location}` : ""}
              </p>
            </div>
            {t.created_at && <span className="hidden text-[12px] text-[#98a2b3] sm:block">{String(t.created_at).slice(0, 10)}</span>}
            <ChevronRight size={18} className="shrink-0 text-[#98a2b3]" />
          </Link>
        ))}
      </div>
    </div>
  );
}

export default TendersList;

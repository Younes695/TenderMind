import { useEffect, useMemo, useState } from "react";
import { Newspaper, RefreshCw, ExternalLink, CheckCircle2, XCircle, AlertTriangle, ScanSearch } from "lucide-react";
import { Link } from "react-router-dom";
import apiClient from "../api/client";
import { useT } from "../i18n";

const OPEN_TYPES = /invitation|request for (bids|proposals|quotations|expression)|general procurement|prequalification/i;

function fmt(d) {
  return d ? new Date(d).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : "-";
}

const FIT_STYLE = { STRONG: "bg-[#e7f4ec] text-[#1f7a4d]", FAIR: "bg-[#fdf3dc] text-[#8a6a22]", WEAK: "bg-[#fdecec] text-[#a33a3a]" };
const ICON = { MET: [CheckCircle2, "text-[#1f7a4d]"], PARTIAL: [AlertTriangle, "text-[#b7791f]"], NOT_MET: [XCircle, "text-[#a33a3a]"] };

/** Why this notice matches (or not) the company's capabilities — every factor shown. */
function Fit({ fit }) {
  const t = useT();
  if (!fit) return null;
  return (
    <div data-testid="notice-fit" className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px]">
      {fit.match == null
        ? <span className="rounded-md bg-[#f2f4f7] px-2 py-0.5 font-bold text-[#667085]">{t("Match: insufficient data")}</span>
        : <span className={`rounded-md px-2 py-0.5 font-bold ${FIT_STYLE[fit.status] || ""}`}>{t("Match {n}%", { n: fit.match })}</span>}
      {fit.factors.map((f) => {
        const [Icon, cls] = ICON[f.status] || ICON.PARTIAL;
        return <span key={f.factor} className="flex items-center gap-1 text-[#475467]"><Icon size={13} className={cls} /> {t(f.key, { ...f.vars, kind: f.vars.kind ? t(f.vars.kind) : undefined })}</span>;
      })}
    </div>
  );
}

/** Tender notices from official sources (World Bank procurement notices API,
 *  plus any trusted feeds the server administrator allow-lists). */
export default function News() {
  const t = useT();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [country, setCountry] = useState("");
  const [query, setQuery] = useState("");
  const [openOnly, setOpenOnly] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [sort, setSort] = useState("match");

  const load = () => apiClient.getNews({ country, q: query, sort }).then(setData).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [country, sort]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = async () => {
    setRefreshing(true);
    try { await apiClient.refreshNews(); await load(); } catch (e) { setError(e.message); } finally { setRefreshing(false); }
  };

  const now = Date.now();
  const items = useMemo(() => (data?.items || []).filter((n) => !openOnly
    || (n.deadline_at ? new Date(n.deadline_at).getTime() >= now : OPEN_TYPES.test(n.notice_type || ""))), [data, openOnly, now]);

  return (
    <div className="mx-auto max-w-[1100px] space-y-4 p-4 sm:p-6 lg:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-[24px] font-black text-[#101828]"><Newspaper size={22} /> {t("Tender Radar")}</h1>
          <p className="mt-1 text-[14px] text-[#667085]">
            {t("Electricity-sector tenders from official sources. Sources:")} {(data?.sources || ["World Bank procurement notices"]).join(", ")}.
          </p>
          {data?.last_refresh?.at && <p className="text-[12px] text-[#98a2b3]">{t("Last updated")} {new Date(data.last_refresh.at).toLocaleString()}</p>}
        </div>
        <button type="button" onClick={refresh} disabled={refreshing}
          className="flex items-center gap-1.5 rounded-lg bg-[#162A4C] px-4 py-2 text-[14px] font-semibold text-white disabled:opacity-50">
          <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} /> {refreshing ? t("Updating…") : t("Update now")}
        </button>
      </div>
      <form className="flex flex-wrap items-center gap-3" onSubmit={(e) => { e.preventDefault(); load(); }}>
        <select aria-label="Country" value={country} onChange={(e) => setCountry(e.target.value)} className="rounded-lg border border-[#d0d5dd] bg-white px-3 py-2 text-[14px]">
          <option value="">{t("All countries")}</option>
          {(data?.countries || []).map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <input aria-label="Search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("Search (e.g. substation, 132 kV)")}
          className="min-w-[220px] flex-1 rounded-lg border border-[#d0d5dd] px-3 py-2 text-[14px]" />
        <select aria-label={t("Sort by")} value={sort} onChange={(e) => setSort(e.target.value)} className="rounded-lg border border-[#d0d5dd] bg-white px-3 py-2 text-[14px]">
          <option value="match">{t("Best match first")}</option>
          <option value="date">{t("Newest first")}</option>
        </select>
        <label className="flex items-center gap-2 text-[13px] text-[#344054]">
          <input type="checkbox" checked={openOnly} onChange={(e) => setOpenOnly(e.target.checked)} /> {t("Open for bidding only")}
        </label>
      </form>
      {data && (
        <div data-testid="radar-summary" className="flex flex-wrap gap-2 text-[13px]">
          <span className="rounded-lg border border-[#e8e4dc] bg-white px-3 py-1.5"><b className="text-[#101828]">{items.length}</b> {t("notices")}</span>
          <span className="rounded-lg border border-[#cfe6d8] bg-[#f1f8f4] px-3 py-1.5 text-[#1f7a4d]"><b>{items.filter((n) => n.fit?.status === "STRONG").length}</b> {t("strong matches")}</span>
          <span className="rounded-lg border border-[#f0dfb8] bg-[#fdf8ec] px-3 py-1.5 text-[#8a6a22]"><b>{data.summary?.closing_this_week ?? 0}</b> {t("closing this week")}</span>
          {!data.capabilities_set && <Link to="/settings" className="rounded-lg px-3 py-1.5 font-semibold text-[#162A4C] underline">{t("Fill your capabilities in Settings to see match %")}</Link>}
        </div>
      )}
      {error && <div data-testid="error-banner" className="rounded-xl border border-[#f5c6c6] bg-[#fdf0f0] p-3 text-[14px] text-[#a33a3a]">{error}</div>}
      {!data ? <div className="p-2 text-[14px] text-[#667085]">{t("Loading…")}</div> : items.length === 0 ? (
        <div data-testid="empty-state" className="rounded-xl border border-[#e8e4dc] bg-white p-6 text-[14px] text-[#667085]">
          {t("No notices match.")} {data.count === 0 ? t('Press "Update now" to fetch the latest.') : t('Try another country or turn off "Open for bidding only".')}
        </div>
      ) : (
        <ul className="space-y-3">
          {items.map((n) => (
            <li key={n.id} data-testid="news-item" className="rounded-xl border border-[#e8e4dc] bg-white p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="text-[15px] font-bold text-[#101828]">{n.title}</p>
                {n.notice_type && <span className="rounded-md bg-[#eef2f8] px-2 py-0.5 text-[11px] font-bold text-[#162A4C]">{n.notice_type}</span>}
              </div>
              {n.description && <p className="mt-1 text-[13px] text-[#475467]">{n.description}</p>}
              <Fit fit={n.fit} />
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-[#667085]">
                <span>{n.country || "-"}</span>
                {n.organization && <span>{n.organization}</span>}
                <span>{t("Published")} {fmt(n.published_at)}</span>
                <span className={n.deadline_at ? "font-semibold text-[#8a6a22]" : ""}>{t("Deadline")} {fmt(n.deadline_at)}</span>
                <span>{t("Source")}: {n.source}</span>
                <Link data-testid="analyze-notice" to={`/tenders/new?${new URLSearchParams({ title: n.title || "", client: n.organization || "", location: n.country || "" })}`}
                  className="flex items-center gap-1 font-semibold text-[#162A4C] underline"><ScanSearch size={12} /> {t("Analyze tender")}</Link>
                {n.url && (
                  <a href={n.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 font-semibold text-[#162A4C] underline">
                    {t("Open notice")} <ExternalLink size={12} />
                  </a>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

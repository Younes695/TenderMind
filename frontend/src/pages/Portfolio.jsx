import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Gavel, Stamp, Layers, FolderSearch, BarChart3, FileText, Search, ShieldAlert, Handshake } from "lucide-react";
import apiClient from "../api/client";
import { usePrefs } from "../i18n";
import { STAGE_LABEL } from "../components/TenderIntel";
import { WorkspaceLoading } from "../components/TenderLoading";

/** Stage 9 — portfolio pages across all the account's tenders. */

const BAND = { GO: ["Go|band", "bg-[#1f7a4d]"], REVIEW: ["Review|band", "bg-[#a98238]"], NO_GO: ["No-Go|band", "bg-[#b42318]"] };
const FINAL = { GO: ["Go|final", "bg-[#e7f5ee] text-[#1f7a4d]"], NO_GO: ["No-Go|final", "bg-[#fdf0f0] text-[#b42318]"] };
const card = "rounded-2xl border border-[#e5e1d9] bg-white p-5";
const primary = "rounded-lg bg-[#162A4C] px-4 py-2 text-[14px] font-semibold text-white disabled:opacity-50";

function Page({ icon: Icon, title, intro, children, testid }) {
  const { t } = usePrefs();
  return (
    <main data-testid={testid} className="min-h-screen bg-[#f8f7f3] p-4 sm:p-6 lg:p-8">
      <div className="mx-auto max-w-[1300px] space-y-4">
        <div>
          <h1 className="flex items-center gap-2 text-[22px] font-black text-[#101828]"><Icon size={22} /> {t(title)}</h1>
          {intro && <p className="mt-1 text-[14px] text-[#667085]">{t(intro)}</p>}
        </div>
        {children}
      </div>
    </main>
  );
}

function useData(loader, deps = []) {
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { loader().then((x) => setD(x ?? null)).catch((e) => setError(e.message)); }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  return [d, error, setD];
}

const Err = ({ error }) => (error ? <div data-testid="error-banner" className="rounded-xl border border-[#f5c6c6] bg-[#fdf0f0] p-3 text-[14px] text-[#a33a3a]">{error}</div> : null);

// ---------- Decision board (replaces the old Go / No-Go page)
export function DecisionBoard() {
  const { t } = usePrefs();
  const [rows, error] = useData(() => apiClient.getBoard());
  const [sort, setSort] = useState("deadline");
  const sorted = useMemo(() => {
    const list = Array.isArray(rows) ? [...rows] : [];
    if (sort === "score") list.sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
    else list.sort((a, b) => (a.deadline || "9999").localeCompare(b.deadline || "9999"));
    return list;
  }, [rows, sort]);
  return (
    <Page icon={Gavel} title="Decision board" testid="decision-board"
      intro="Every tender side by side: score, eligibility, certificates, department votes and deadline. The decision belongs to your authorised team.">
      <Err error={error} />
      {rows === null && !error ? <WorkspaceLoading /> : (
        <section className={card}>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-[13px] text-[#667085]">{t("{n} tender(s)", { n: sorted.length })}</p>
            <label className="text-[13px] text-[#344054]">{t("Sort by")}{" "}
              <select value={sort} onChange={(e) => setSort(e.target.value)} className="rounded-lg border border-[#d0d5dd] px-2 py-1">
                <option value="deadline">{t("Deadline")}</option><option value="score">{t("Score")}</option>
              </select></label>
          </div>
          {sorted.length === 0 ? <p data-testid="empty-state" className="text-[14px] text-[#667085]">{t("No tenders yet — create a tender to see decision support.")}</p> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-start text-[13px]">
                <thead><tr className="text-[12px] text-[#667085]">
                  {["Tender", "Score", "Eligibility", "Certificates", "Votes", "Stage", "Deadline", "Decision", ""].map((h) => <th key={h} className="py-2 text-start">{t(h)}</th>)}
                </tr></thead>
                <tbody>
                  {sorted.map((r) => {
                    const [bl, bg] = BAND[r.band] || ["—", "bg-[#98a2b3]"];
                    return (
                      <tr key={r.id} data-testid="board-row" className="border-t border-[#f0ede6] align-middle">
                        <td className="py-2 pe-2"><Link to={`/tenders/${encodeURIComponent(r.id)}`} className="font-bold text-[#162A4C] underline">{r.title || r.id}</Link>
                          <span className="block text-[11px] text-[#98a2b3]">{[r.id, r.client].filter(Boolean).join(" · ")}</span></td>
                        <td><span className={`inline-block w-14 rounded px-1.5 py-0.5 text-center text-[12px] font-bold text-white ${bg}`}>{r.score ?? "—"}</span>
                          <span className="block text-[11px] text-[#667085]">{t(bl)}</span></td>
                        <td>{r.eligibility === "INELIGIBLE" ? <span className="text-[#b42318]">{r.overridden ? t("Continued anyway") : t("Does not fit")}</span>
                          : r.eligibility === "ELIGIBLE" ? <span className="text-[#1f7a4d]">{t("Fits")}{r.eligibility_percent != null ? ` · ${r.eligibility_percent}%` : ""}</span> : <span className="text-[#98a2b3]">{t("Not checked")}</span>}</td>
                        <td>{r.needs_partner ? <span className="flex items-center gap-1 text-[#8a6a22]"><Handshake size={13} /> {t("Needs a partner")}</span> : <span className="text-[#98a2b3]">—</span>}</td>
                        <td>{r.votes?.total ? `${r.votes.approve_pct ?? "—"}% (${r.votes.approve}/${r.votes.approve + r.votes.reject})` : <span className="text-[#98a2b3]">—</span>}</td>
                        <td>{r.stage ? t(STAGE_LABEL[r.stage]) : <span className="text-[#98a2b3]">—</span>}</td>
                        <td>{r.deadline || <span className="text-[#98a2b3]">—</span>}</td>
                        <td>{r.final_decision ? <span className={`rounded px-2 py-0.5 text-[11px] font-bold ${FINAL[r.final_decision][1]}`}>{t(FINAL[r.final_decision][0])}</span> : <span className="text-[#98a2b3]">{t("Open")}</span>}</td>
                        <td><Link to={`/tenders/${encodeURIComponent(r.id)}/pack`} className="text-[12px] font-semibold text-[#162A4C] underline">{t("Decision pack")}</Link></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-3 text-[12px] text-[#667085]">{t("A score appears once the tender has been analysed. It never replaces your team's decision.")}</p>
        </section>
      )}
    </Page>
  );
}

// ---------- Approvals
function DecideForm({ row, onSaved }) {
  const { t } = usePrefs();
  const [f, setF] = useState({ decision: "GO", reason: "", by: "" });
  const [error, setError] = useState(null);
  const save = async (e) => {
    e.preventDefault();
    if (!f.reason.trim()) { setError(t("Write the reason for the decision")); return; }
    try { await apiClient.setFinalDecision(row.id, f); onSaved(); } catch (err) { setError(err.message); }
  };
  const input = "w-full min-w-0 rounded-lg border border-[#d0d5dd] px-3 py-2 text-[14px]";
  return (
    <form onSubmit={save} className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-[auto_1fr_2fr_auto]">
      <select className={input} value={f.decision} onChange={(e) => setF({ ...f, decision: e.target.value })} aria-label={t("Decision")}>
        <option value="GO">{t("Go|final")}</option><option value="NO_GO">{t("No-Go|final")}</option>
      </select>
      <input className={input} placeholder={t("Your name")} value={f.by} onChange={(e) => setF({ ...f, by: e.target.value })} maxLength={120} />
      <input className={input} placeholder={t("Reason (required)")} value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} maxLength={2000} />
      <button type="submit" className={primary} data-testid={`decide-${row.id}`}>{t("Record decision")}</button>
      {error && <p className="text-[13px] text-[#b42318] sm:col-span-2">{error}</p>}
    </form>
  );
}

export function Approvals() {
  const { t } = usePrefs();
  const [d, error, setD] = useData(() => apiClient.getApprovals());
  const reload = () => apiClient.getApprovals().then(setD).catch(() => {});
  const Votes = ({ v }) => (v.overall.total
    ? <span className="text-[12px] text-[#475467]">{t("{a} approve, {r} reject, {x} abstain", { a: v.overall.approve, r: v.overall.reject, x: v.overall.abstain })}{v.overall.approve_pct != null ? ` · ${v.overall.approve_pct}%` : ""}</span>
    : <span className="text-[12px] text-[#98a2b3]">{t("No department votes yet.")}</span>);
  return (
    <Page icon={Stamp} title="Approvals" testid="approvals"
      intro="Department votes feed the decision; the tender manager records the final Go / No-Go with a reason. Every decision is kept in the audit trail.">
      <Err error={error} />
      {!d && !error ? <WorkspaceLoading /> : d && (
        <>
          <section className={card}>
            <h2 className="mb-2 text-[16px] font-bold text-[#101828]">{t("Waiting for a decision")} ({d.waiting.length})</h2>
            {d.waiting.length === 0 ? <p className="text-[13px] text-[#667085]">{t("Nothing waiting.")}</p> : (
              <ul className="space-y-3">{d.waiting.map((r) => (
                <li key={r.id} className="rounded-xl border border-[#eef0f3] p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link to={`/tenders/${encodeURIComponent(r.id)}`} className="font-bold text-[#162A4C] underline">{r.title || r.id}</Link>
                    {r.deadline && <span className="text-[12px] text-[#667085]">{t("Submission deadline")}: {r.deadline}</span>}
                    <Link to={`/tenders/${encodeURIComponent(r.id)}/pack`} className="ms-auto text-[12px] font-semibold text-[#162A4C] underline">{t("Decision pack")}</Link>
                  </div>
                  <Votes v={r.votes} />
                  <DecideForm row={r} onSaved={reload} />
                </li>))}</ul>)}
          </section>
          <section className={card}>
            <h2 className="mb-2 text-[16px] font-bold text-[#101828]">{t("Decided")} ({d.decided.length})</h2>
            {d.decided.length === 0 ? <p className="text-[13px] text-[#667085]">{t("No decisions recorded yet.")}</p> : (
              <ul className="space-y-2">{d.decided.map((r) => (
                <li key={r.id} className="text-[13px] text-[#344054]">
                  <span className={`me-2 rounded px-2 py-0.5 text-[11px] font-bold ${FINAL[r.final_decision][1]}`}>{t(FINAL[r.final_decision][0])}</span>
                  <Link to={`/tenders/${encodeURIComponent(r.id)}`} className="font-semibold text-[#162A4C] underline">{r.title || r.id}</Link>
                  <span className="block text-[12px] text-[#667085]">{r.final_reason}{r.final_by ? ` — ${r.final_by}` : ""}{r.final_at ? ` · ${new Date(r.final_at).toLocaleDateString()}` : ""}</span>
                </li>))}</ul>)}
          </section>
        </>
      )}
    </Page>
  );
}

// ---------- Work packages
export function WorkPackages() {
  const { t } = usePrefs();
  const [d, error] = useData(() => apiClient.getWorkPackages());
  return (
    <Page icon={Layers} title="Work Packages" testid="work-packages"
      intro="The technical parts of each tender grouped by discipline, with suppliers you worked with before and the RFQs sent.">
      <Err error={error} />
      {!d && !error ? <WorkspaceLoading /> : Array.isArray(d) && (d.length === 0
        ? <section className={card}><p className="text-[14px] text-[#667085]">{t("No analysed tender yet — process a tender to see its work packages.")}</p></section>
        : d.map((tn) => (
          <section key={tn.id} className={card}>
            <h2 className="mb-2 text-[16px] font-bold"><Link to={`/tenders/${encodeURIComponent(tn.id)}`} className="text-[#162A4C] underline">{tn.title || tn.id}</Link></h2>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {tn.packages.map((p) => (
                <div key={p.discipline} className="rounded-xl bg-[#faf9f6] p-3 text-[13px] text-[#344054]">
                  <p className="font-bold text-[#101828]">{t(p.discipline)}</p>
                  <p className="text-[12px] text-[#667085]">{t("{s} part(s) · {p} pages", { s: p.sections, p: p.pages })}</p>
                  <p className="mt-1">{t("Suggested suppliers from past tenders")}: {p.suppliers.length ? p.suppliers.map((s) => s.contractor).join(t(", ")) : <span className="text-[#98a2b3]">{t("none recorded yet")}</span>}</p>
                  <p>{t("RFQs")}: {p.rfqs.length ? p.rfqs.map((r) => r.reference).join(", ") : <Link to="/subcontractors" className="text-[#162A4C] underline">{t("Create an RFQ")}</Link>}</p>
                </div>
              ))}
            </div>
          </section>
        )))}
    </Page>
  );
}

// ---------- Documents library
export function DocumentsLibrary() {
  const { t } = usePrefs();
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [d, error, setD] = useData(() => apiClient.getDocuments(""));
  const search = (e) => {
    e.preventDefault();
    setQuery(q);
    apiClient.getDocuments(q).then(setD).catch(() => {});
  };
  return (
    <Page icon={FolderSearch} title="Documents" testid="documents-library"
      intro="Every tender file and company document in one place. Search inside the tender texts to find a clause and its page.">
      <Err error={error} />
      <form onSubmit={search} className="flex gap-2">
        <div className="flex flex-1 items-center gap-2 rounded-xl border border-[#e8e4dc] bg-white px-3">
          <Search size={17} className="text-[#98a2b3]" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("Search inside tender documents (e.g. warranty period)")} className="h-[44px] w-full bg-transparent text-[14px] outline-none" />
        </div>
        <button type="submit" className={primary}>{t("Search")}</button>
      </form>
      {d && query && (
        <section className={card} data-testid="document-hits">
          <h2 className="mb-2 text-[15px] font-bold text-[#101828]">{t("{n} match(es) for “{q}”", { n: d.hits.length, q: query })}</h2>
          <ul className="space-y-2">{d.hits.map((h, i) => (
            <li key={i} className="text-[13px] text-[#344054]"><b>{h.file}</b> · {t("page")} {h.page} · <Link className="text-[#162A4C] underline" to={`/tenders/${encodeURIComponent(h.tender_id)}`}>{h.tender_id}</Link>
              <span className="block text-[12px] text-[#667085]" dir="auto">…{h.snippet}…</span></li>))}</ul>
        </section>
      )}
      {!d && !error ? <WorkspaceLoading /> : d && (
        <section className={card}>
          <h2 className="mb-2 text-[15px] font-bold text-[#101828]">{t("All files")} ({d.files.length})</h2>
          <ul className="grid gap-1 text-[13px] text-[#344054] md:grid-cols-2">{d.files.map((f, i) => (
            <li key={i} className="flex items-center gap-2 truncate"><FileText size={13} className="shrink-0 text-[#98a2b3]" />
              <span className="truncate" dir="auto">{f.name}</span>
              <span className="shrink-0 text-[11px] text-[#98a2b3]">{f.kind === "company" ? t("Company document") : f.tender_id}</span></li>))}</ul>
        </section>
      )}
    </Page>
  );
}

// ---------- Analytics
function Bars({ data, labelOf }) {
  const { t } = usePrefs();
  const entries = Object.entries(data || {});
  const max = Math.max(1, ...entries.map(([, v]) => v));
  if (!entries.length) return <p className="text-[13px] text-[#98a2b3]">{t("No data yet.")}</p>;
  return (
    <ul className="space-y-1.5">{entries.map(([k, v]) => (
      <li key={k} className="flex items-center gap-2 text-[13px] text-[#344054]">
        <span className="w-36 shrink-0 truncate">{labelOf ? labelOf(k) : k}</span>
        <span className="h-3 flex-1 overflow-hidden rounded bg-[#f2f4f7]"><span className="block h-full rounded bg-[#162A4C]" style={{ width: `${(100 * v) / max}%` }} /></span>
        <span className="w-8 text-end font-semibold">{v}</span>
      </li>))}</ul>
  );
}

export function Analytics() {
  const { t } = usePrefs();
  const [d, error] = useData(() => apiClient.getAnalytics());
  const OUT = { WON: "Won|outcome", LOST: "Lost|outcome", SUBMITTED: "Submitted|outcome", NOT_SUBMITTED: "Not submitted|outcome" };
  return (
    <Page icon={BarChart3} title="Analytics" testid="analytics" intro="Your bid pipeline and results, from your own tenders.">
      <Err error={error} />
      {!d && !error ? <WorkspaceLoading /> : d && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[["Tenders", d.total], ["Analysed", d.analysed], ["Win rate", d.win_rate != null ? `${d.win_rate}%` : "—"],
              ["Decided (Go / No-Go)", `${d.final_decisions.GO || 0} / ${d.final_decisions.NO_GO || 0}`]].map(([k, v]) => (
              <div key={k} className={card}><p className="text-[12px] text-[#667085]">{t(k)}</p><p className="text-[26px] font-black text-[#101828]">{v}</p></div>
            ))}
          </div>
          {d.win_rate == null && <p className="text-[12px] text-[#667085]">{t("Win rate appears once tenders are marked won or lost.")}</p>}
          <div className="grid gap-4 lg:grid-cols-2">
            <section className={card}><h2 className="mb-2 text-[15px] font-bold">{t("Pipeline by stage")}</h2><Bars data={d.stages} labelOf={(k) => t(STAGE_LABEL[k] || `${k}|stage`)} /></section>
            <section className={card}><h2 className="mb-2 text-[15px] font-bold">{t("Outcomes")}</h2><Bars data={d.outcomes} labelOf={(k) => t(OUT[k] || k)} /></section>
            <section className={card}><h2 className="mb-2 text-[15px] font-bold">{t("Types of work")}</h2><Bars data={d.work_types} labelOf={(k) => t(k)} /></section>
            <section className={card}><h2 className="mb-2 text-[15px] font-bold">{t("New tenders per month")}</h2><Bars data={d.by_month} /></section>
          </div>
          <section className={card}>
            <h2 className="mb-2 text-[15px] font-bold">{t("Top clients")}</h2>
            {d.top_clients.length === 0 ? <p className="text-[13px] text-[#98a2b3]">{t("No data yet.")}</p> : (
              <ul className="space-y-1 text-[13px] text-[#344054]">{d.top_clients.map((c) => (
                <li key={c.client}><b>{t(c.client)}</b> — {t("{n} tender(s), {w} won", { n: c.tenders, w: c.won })}</li>))}</ul>)}
          </section>
        </>
      )}
    </Page>
  );
}

export { ShieldAlert };

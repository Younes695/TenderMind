import { useEffect, useMemo, useState } from "react";
import { Truck, Plus, Trash2, FileText, Copy, X } from "lucide-react";
import apiClient from "../api/client";
import { useT } from "../i18n";
import { confirmRemoval } from "../utils/confirm";

function money(v) {
  if (v == null) return "-";
  if (v >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return String(v);
}

function daysLeft(iso) {
  if (!iso) return null;
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 864e5);
}

function bestReason(text, t) {
  const [head, rest] = String(text).split(": ");
  if (!rest) return t(head);
  return `${t("Best overall score")}: ${rest.split(", ").map((p) => t(p)).join("، ")}`;
}

const EMPTY_RFQ = { reference: "", package_name: "", discipline: "", invited_count: "", closes_at: "", currency: "SAR", scope: "" };
const EMPTY_QUOTE = { contractor: "", price: "", duration_weeks: "", technical_fit: "", payment_terms_days: "" };

/** Subcontractor RFQs per work package: quotations entered by the team, compared
 *  on technical fit, price, duration and payment terms (weights shown on the page). */
export default function Subcontractors() {
  const t = useT();
  const [tenders, setTenders] = useState([]);
  const [rfqs, setRfqs] = useState(null);
  const [activeId, setActiveId] = useState(null);
  const [error, setError] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [rfqForm, setRfqForm] = useState({ tender_id: "", ...EMPTY_RFQ });
  const [quote, setQuote] = useState(EMPTY_QUOTE);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async (keep) => {
    try {
      const d = await apiClient.listRfqs();
      setRfqs(d.rfqs || []);
      setActiveId((cur) => keep || cur || d.rfqs?.[0]?.id || null);
    } catch (e) { setError(e.message); }
  };

  useEffect(() => {
    load();
    apiClient.listTenders().then((l) => {
      const live = (l || []).filter((x) => x.id !== "SA-2018-HV2");
      setTenders(live);
      setRfqForm((f) => ({ ...f, tender_id: f.tender_id || live[0]?.id || "" }));
    }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const rfq = useMemo(() => (rfqs || []).find((r) => r.id === activeId) || null, [rfqs, activeId]);
  const replace = (updated) => setRfqs((list) => list.map((r) => (r.id === updated.id ? updated : r)));

  const run = async (fn) => {
    setBusy(true); setError(null);
    try { await fn(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  const createRfq = (e) => {
    e.preventDefault();
    run(async () => {
      const { tender_id, ...data } = rfqForm;
      const created = await apiClient.createRfq(tender_id, data);
      setShowNew(false);
      setRfqForm({ tender_id, ...EMPTY_RFQ });
      await load(created.id);
      setActiveId(created.id);
    });
  };

  const addQuote = (e) => {
    e.preventDefault();
    run(async () => { replace(await apiClient.addQuotation(rfq.id, quote)); setQuote(EMPTY_QUOTE); });
  };

  const input = "rounded-lg border border-[#d0d5dd] px-3 py-2 text-[14px] outline-none focus:border-[#162A4C]";
  const primary = "flex items-center gap-1.5 rounded-lg bg-[#162A4C] px-4 py-2 text-[14px] font-semibold text-white disabled:opacity-50";
  const left = daysLeft(rfq?.closes_at);

  return (
    <div className="mx-auto max-w-[1300px] space-y-5 p-4 sm:p-6 lg:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[24px] font-black text-[#101828]">{t("Subcontractor RFQs · Comparison")}</h1>
          <p className="text-[14px] text-[#667085]">
            {rfq ? t("{name} · {n} quotations received", { name: rfq.package_name, n: rfq.quoted_count }) : t("Request quotations per work package and compare them.")}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {rfqs?.length > 0 && (
            <select aria-label={t("RFQ")} value={activeId || ""} onChange={(e) => setActiveId(e.target.value)} className={input}>
              {rfqs.map((r) => <option key={r.id} value={r.id}>{r.reference} - {r.package_name} ({r.tender_id})</option>)}
            </select>
          )}
          <button type="button" onClick={() => setShowNew((v) => !v)} className={primary} disabled={!tenders.length}>
            <Plus size={15} /> {t("New RFQ")}
          </button>
        </div>
      </div>

      {error && <div data-testid="error-banner" className="rounded-xl border border-[#f5c6c6] bg-[#fdf0f0] p-3 text-[14px] text-[#a33a3a]">{error}</div>}

      {showNew && (
        <form onSubmit={createRfq} data-testid="new-rfq" className="grid gap-3 rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-[13px] text-[#344054]">{t("Tender")}
            <select className={`${input} w-full`} value={rfqForm.tender_id} onChange={(e) => setRfqForm({ ...rfqForm, tender_id: e.target.value })}>
              {tenders.map((x) => <option key={x.id} value={x.id}>{x.id}</option>)}
            </select>
          </label>
          {[["reference", "Reference (e.g. RFQ-MECH-04)"], ["package_name", "Work package"], ["discipline", "Discipline (e.g. HVAC)"]].map(([k, label]) => (
            <label key={k} className="text-[13px] text-[#344054]">{t(label)}
              <input className={`${input} w-full`} value={rfqForm[k]} onChange={(e) => setRfqForm({ ...rfqForm, [k]: e.target.value })} required={k !== "discipline"} />
            </label>
          ))}
          <label className="text-[13px] text-[#344054]">{t("Contractors invited")}
            <input type="number" min="0" className={`${input} w-full`} value={rfqForm.invited_count} onChange={(e) => setRfqForm({ ...rfqForm, invited_count: e.target.value })} />
          </label>
          <label className="text-[13px] text-[#344054]">{t("Closes on")}
            <input type="date" className={`${input} w-full`} value={rfqForm.closes_at} onChange={(e) => setRfqForm({ ...rfqForm, closes_at: e.target.value })} />
          </label>
          <label className="text-[13px] text-[#344054]">{t("Currency")}
            <select className={`${input} w-full`} value={rfqForm.currency} onChange={(e) => setRfqForm({ ...rfqForm, currency: e.target.value })}>
              {["SAR", "EGP", "AED", "USD"].map((c) => <option key={c}>{c}</option>)}
            </select>
          </label>
          <label className="text-[13px] text-[#344054]">{t("Scope keywords (optional)")}
            <input className={`${input} w-full`} placeholder="chiller, duct, ventilation" value={rfqForm.scope} onChange={(e) => setRfqForm({ ...rfqForm, scope: e.target.value })} />
          </label>
          <div className="flex items-end"><button type="submit" className={primary} disabled={busy}>{t("Create RFQ")}</button></div>
        </form>
      )}

      {rfqs === null ? <div className="p-2 text-[14px] text-[#667085]">{t("Loading…")}</div> : !rfq ? (
        <div data-testid="empty-state" className="rounded-2xl border border-[#e8e4dc] bg-white p-6 text-[14px] text-[#667085]">
          {tenders.length ? t("No RFQs yet. Create one for a work package, then add the quotations you receive.") : t("Create a tender first.")}
        </div>
      ) : (
        <>
          <section className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#e8e4dc] bg-white p-5">
            <div className="flex items-center gap-3">
              <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#eef2f8] text-[#162A4C]"><Truck size={20} /></span>
              <div>
                <p className="text-[18px] font-bold text-[#101828]">{rfq.package_name} <span className="text-[#667085]">|</span> {rfq.reference}</p>
                <p className="text-[13px] text-[#667085]">
                  {[rfq.discipline,
                    rfq.invited_count != null ? t("sent to {n} contractors", { n: rfq.invited_count }) : null,
                    t("{n} quoted", { n: rfq.quoted_count }),
                    left != null ? (left >= 0 ? t("closes in {n} days", { n: left }) : t("closed")) : null,
                    rfq.status === "AWARDED" ? t("awarded") : null].filter(Boolean).join(" · ")}
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <button type="button" className={primary} onClick={() => run(async () => setDraft(await apiClient.getRfqDraft(rfq.id)))}><FileText size={15} /> {t("Generate RFQ")}</button>
              <button type="button" aria-label={t("Delete RFQ")} className="rounded-lg border border-[#d0d5dd] px-3 text-[#a33a3a]"
                onClick={() => confirmRemoval(rfq.reference, "RFQ") && run(async () => { await apiClient.deleteRfq(rfq.id); setActiveId(null); await load(); })}><Trash2 size={15} /></button>
            </div>
          </section>

          <section className="overflow-x-auto rounded-2xl border border-[#e8e4dc] bg-white">
            <table className="w-full min-w-[760px] text-[14px]">
              <thead className="bg-[#faf9f6] text-[13px] text-[#667085]">
                <tr>{["Contractor", `Price (${rfq.currency})`, "Duration", "Technical Fit", "Terms", "Score", "Action"].map((h) => <th key={h} className="px-5 py-3 text-start font-semibold">{t(h)}</th>)}</tr>
              </thead>
              <tbody>
                {rfq.quotations.map((q) => (
                  <tr key={q.id} data-testid="quote-row" className={`border-t border-[#eeeae3] ${q.is_best ? "bg-[#fdf8ec]" : ""}`}>
                    <td className="px-5 py-4 font-bold text-[#101828]">
                      {q.contractor} {q.is_best && <span data-testid="best-badge" className="ms-2 rounded-md bg-[#C8A96B] px-2 py-0.5 text-[11px] font-bold text-[#162A4C]">{t("BEST")}</span>}
                      {q.selected && <span className="ms-2 rounded-md bg-[#e7f5ee] px-2 py-0.5 text-[11px] font-bold text-[#1f7a4d]">{t("Selected")}</span>}
                      {q.is_best && q.best_reason && <p className="text-[12px] font-normal text-[#8a6a22]">{bestReason(q.best_reason, t)}</p>}
                      {q.note && <p className="text-[12px] font-normal text-[#b42318]">{t(q.note)}</p>}
                    </td>
                    <td className="px-5 py-4 font-bold text-[#101828]">{money(q.price)}</td>
                    <td className="px-5 py-4 text-[#667085]">{t("{n} wks", { n: q.duration_weeks })}</td>
                    <td className={`px-5 py-4 font-bold ${q.technical_fit >= 60 ? "text-[#1f7a4d]" : "text-[#b42318]"}`}>{q.technical_fit}%</td>
                    <td className="px-5 py-4 text-[#667085]">{t("{n} days", { n: q.payment_terms_days })}</td>
                    <td className="px-5 py-4 text-[#344054]" title={t("Technical fit 40% · Price 35% · Duration 15% · Payment terms 10%")}>{q.score}</td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <button type="button" disabled={busy || q.selected} className="font-bold text-[#162A4C] disabled:opacity-40"
                          onClick={() => run(async () => replace(await apiClient.selectQuotation(q.id)))}>{t("Select")}</button>
                        <button type="button" aria-label={t("Remove quotation")} className="text-[#98a2b3] hover:text-[#a33a3a]"
                          onClick={() => confirmRemoval(q.contractor, "quotation") && run(async () => replace(await apiClient.deleteQuotation(q.id)))}><Trash2 size={14} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
                <tr className="border-t border-[#eeeae3] bg-[#fafaf8]">
                  <td colSpan={7} className="px-5 py-3">
                    <form onSubmit={addQuote} data-testid="add-quote" className="flex flex-wrap items-end gap-2">
                      {[["contractor", "Contractor", "text"], ["price", "Price", "number"], ["duration_weeks", "Weeks", "number"],
                        ["technical_fit", "Technical fit %", "number"], ["payment_terms_days", "Terms (days)", "number"]].map(([k, label, type]) => (
                        <label key={k} className="text-[12px] text-[#667085]">{t(label)}
                          <input type={type} step="any" min="0" max={k === "technical_fit" ? 100 : undefined} required value={quote[k]}
                            onChange={(e) => setQuote({ ...quote, [k]: e.target.value })} className={`${input} block ${k === "contractor" ? "w-48" : "w-28"}`} />
                        </label>
                      ))}
                      <button type="submit" className={primary} disabled={busy}><Plus size={14} /> {t("Add quotation")}</button>
                    </form>
                  </td>
                </tr>
              </tbody>
            </table>
          </section>
          <p className="text-[12px] text-[#667085]">{t("Best = highest score among quotations with at least 60% technical fit. Weights: technical fit 40% · price 35% · duration 15% · payment terms 10%.")}</p>
        </>
      )}

      {draft && (
        <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="flex max-h-[85vh] w-full max-w-[760px] flex-col rounded-2xl bg-white p-5">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-[16px] font-bold text-[#101828]">{t("RFQ draft")} · {t("{n} requirements from the tender", { n: draft.requirements_used })}</p>
              <button type="button" aria-label={t("Close")} onClick={() => setDraft(null)}><X size={18} /></button>
            </div>
            <pre dir="ltr" className="flex-1 overflow-auto whitespace-pre-wrap rounded-lg bg-[#faf9f6] p-4 text-[13px] text-[#344054]">{draft.text}</pre>
            <div className="mt-3 flex gap-2">
              <button type="button" className={primary} onClick={() => navigator.clipboard?.writeText(draft.text)}><Copy size={14} /> {t("Copy")}</button>
              <a className="rounded-lg border border-[#d0d5dd] px-4 py-2 text-[14px] font-semibold text-[#162A4C]"
                href={`data:text/plain;charset=utf-8,${encodeURIComponent(draft.text)}`} download={`${rfq?.reference || "RFQ"}.txt`}>{t("Download .txt")}</a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

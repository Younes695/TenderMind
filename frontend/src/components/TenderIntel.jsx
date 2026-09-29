import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Compass, CalendarClock, History, StickyNote, Trash2, ArrowUpRight } from "lucide-react";
import apiClient from "../api/client";
import { useT } from "../i18n";
import { tx } from "./BidTools";

/** Stage 8 — tender page: quick summary with "what you need to do", stage and submission deadline,
 *  similar past tenders / client history, and notes. */

const input = "w-full min-w-0 rounded-lg border border-[#d0d5dd] px-3 py-2 text-[14px] outline-none focus:border-[#162A4C]";
const primary = "rounded-lg bg-[#162A4C] px-4 py-2 text-[14px] font-semibold text-white disabled:opacity-50";
export const STAGES = ["ELIGIBILITY", "STUDY", "PRICING", "SUBMISSION", "SUBMITTED", "CLOSED"];
export const STAGE_LABEL = { ELIGIBILITY: "Eligibility|stage", STUDY: "Study|stage", PRICING: "Pricing|stage",
  SUBMISSION: "Submission|stage", SUBMITTED: "Submitted|stage", CLOSED: "Closed|stage" };

function Fact({ label, value, source }) {
  const t = useT();
  if (value == null || value === "") return null;
  return (
    <div className="rounded-xl bg-[#faf9f6] p-3">
      <p className="text-[12px] text-[#667085]">{t(label)}</p>
      <p className="text-[15px] font-bold text-[#101828]">{value}</p>
      {source && <p className="text-[11px] text-[#98a2b3]">{source.file} · {t("page")} {source.page}</p>}
    </div>
  );
}

export function SummaryCard({ tenderId, onPlanChange }) {
  const t = useT();
  const [s, setS] = useState(null);
  const [plan, setPlanState] = useState({ stage: "", submission_deadline: "" });
  const [msg, setMsg] = useState(null);
  useEffect(() => {
    apiClient.getSummary(tenderId).then((d) => {
      if (!d || !d.tender) return;
      setS(d);
      setPlanState({ stage: d.tender.stage || "", submission_deadline: d.tender.submission_deadline || "" });
    }).catch(() => {});
  }, [tenderId]);
  if (!s) return null;
  const savePlan = async (patch) => {
    const next = { ...plan, ...patch };
    setPlanState(next);
    try { await apiClient.setPlan(tenderId, patch); setMsg(t("Saved")); onPlanChange?.(next); } catch (err) { setMsg(err.message); }
  };
  const f = s.facts || {};
  const cs = s.certificates || {};
  return (
    <section data-testid="tender-summary" className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
      <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><Compass size={18} /> {t("Quick summary")}</h2>
      <div className="mt-3 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <Fact label="Client" value={s.client?.name} source={s.client?.evidence} />
        <Fact label="Type of work" value={f.work_type ? t(f.work_type) : null} />
        <Fact label="Voltage" value={f.voltage_kv ? `${f.voltage_kv} kV` : null} />
        <Fact label="Country" value={f.country ? t(f.country) : null} />
        <Fact label="Documents" value={f.documents ? t("{d} files · {p} pages", { d: f.documents, p: f.pages }) : null} />
        <Fact label="Mandatory requirements" value={f.requirements ? t("{m} of {n}", { m: f.mandatory, n: f.requirements }) : null} />
      </div>
      {(s.dates || []).length > 0 && (
        <ul className="mt-3 space-y-1 text-[13px] text-[#344054]">
          {s.dates.map((d, i) => (
            <li key={i}><CalendarClock size={13} className="me-1 inline" /> <b>{t(d.label)}:</b> {d.date}
              {d.source && <span className="text-[12px] text-[#98a2b3]"> — {d.source.file} · {t("page")} {d.source.page}</span>}
              {d.set_by_team && <span className="text-[12px] text-[#1f7a4d]"> ({t("set by the team")})</span>}</li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <label className="text-[13px] text-[#344054]">{t("Stage")}
          <select data-testid="tender-stage" className={input} value={plan.stage} onChange={(e) => savePlan({ stage: e.target.value })}>
            <option value="">{t("Not set")}</option>
            {STAGES.map((x) => <option key={x} value={x}>{t(STAGE_LABEL[x])}</option>)}
          </select>
        </label>
        <label className="text-[13px] text-[#344054]">{t("Submission deadline")}
          <input type="date" data-testid="tender-deadline" className={input} value={plan.submission_deadline}
            onChange={(e) => savePlan({ submission_deadline: e.target.value })} />
        </label>
        {s.suggested_deadline?.date && !plan.submission_deadline && (
          <button type="button" data-testid="use-suggested-deadline" className="rounded-lg border border-[#162A4C] px-3 py-2 text-[13px] font-semibold text-[#162A4C]"
            onClick={() => savePlan({ submission_deadline: s.suggested_deadline.date })}>
            {t("Use {date} from {file} p. {page}", { date: s.suggested_deadline.date, file: s.suggested_deadline.file, page: s.suggested_deadline.page })}
          </button>
        )}
        {msg && <span className="text-[12px] text-[#1f7a4d]">{msg}</span>}
      </div>
      {(cs.needs_partner || s.contradictions > 0 || s.eligibility?.status === "INELIGIBLE") && (
        <p className="mt-3 rounded-lg bg-[#fdf4de] p-2.5 text-[13px] text-[#8a6a22]">
          {[s.eligibility?.status === "INELIGIBLE" && !s.eligibility.overridden ? t("Does not fit the company") : null,
            cs.needs_partner ? t("Needs a partner or supplier for certificates") : null,
            s.contradictions ? t("{n} contradiction(s) in the documents", { n: s.contradictions }) : null].filter(Boolean).join(" · ")}
        </p>
      )}
      {(s.actions || []).length > 0 && (
        <div className="mt-4">
          <p className="text-[14px] font-bold text-[#101828]">{t("What you need to do")}</p>
          <ol data-testid="summary-actions" className="mt-1 list-decimal space-y-1 ps-5 text-[13px] text-[#344054]">
            {s.actions.map((a, i) => <li key={i}>{tx(t, a.key, a.vars, a.text)}</li>)}
          </ol>
        </div>
      )}
    </section>
  );
}

const DEC = { BID: "Go|band", REVIEW: "Review|band", NO_GO: "No-Go|band" };
const OUT = { WON: "Won|outcome", LOST: "Lost|outcome", SUBMITTED: "Submitted|outcome", NOT_SUBMITTED: "Not submitted|outcome" };

export function SimilarCard({ tenderId }) {
  const t = useT();
  const [d, setD] = useState(null);
  const [open, setOpen] = useState(false);
  useEffect(() => { if (open && !d) apiClient.getSimilar(tenderId).then(setD).catch(() => setD({ similar: [], client_history: [] })); }, [open, d, tenderId]);
  return (
    <section data-testid="similar-tenders" className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><History size={18} /> {t("Similar tenders and client history")}</h2>
        <button type="button" data-testid="open-similar" className={primary} onClick={() => setOpen(!open)}>{open ? t("Hide") : t("Show")}</button>
      </div>
      {open && d && (
        <div className="mt-3 space-y-3">
          {d.client_history?.length > 0 && (
            <p className="rounded-lg bg-[#eef2f8] p-2.5 text-[13px] text-[#162A4C]">
              {t("You took part in {n} earlier tender(s) with {client}.", { n: d.client_history.length, client: d.client })}
            </p>
          )}
          {!d.similar?.length ? <p className="text-[13px] text-[#667085]">{t("No similar earlier tender found.")}</p> : (
            <ul className="space-y-2">
              {d.similar.map((x) => (
                <li key={x.id} className="rounded-lg border border-[#eef0f3] p-3 text-[13px] text-[#344054]">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link to={`/tenders/${encodeURIComponent(x.id)}`} className="font-bold text-[#162A4C] underline">{x.title || x.id}</Link>
                    <span className="rounded bg-[#162A4C] px-2 py-0.5 text-[11px] font-bold text-white">{t("{s}% similar", { s: x.score })}</span>
                    {x.decision && <span className="text-[12px]">{t("Recommendation")}: {t(DEC[x.decision] || x.decision)}</span>}
                    {x.outcome && <span className="text-[12px] font-semibold">{t(OUT[x.outcome] || x.outcome)}</span>}
                    <Link to={`/tenders/${encodeURIComponent(x.id)}`} aria-label={t("Open")} className="ms-auto text-[#162A4C]"><ArrowUpRight size={15} /></Link>
                  </div>
                  <p className="mt-1 text-[12px] text-[#667085]">{x.reasons.map((r) => tx(t, r.key, r.vars)).join(" · ")}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

export function NotesCard({ tenderId }) {
  const t = useT();
  const [notes, setNotes] = useState([]);
  const [form, setForm] = useState({ author: "", text: "" });
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(false);
  useEffect(() => { if (open) apiClient.listNotes(tenderId).then((d) => setNotes(Array.isArray(d) ? d : [])).catch(() => {}); }, [open, tenderId]);
  const add = async (e) => {
    e.preventDefault();
    if (!form.text.trim()) { setError(t("Write the note first")); return; }
    try { const n = await apiClient.addNote(tenderId, form); setNotes([n, ...notes]); setForm({ ...form, text: "" }); setError(null); }
    catch (err) { setError(err.message); }
  };
  const remove = async (n) => {
    try { await apiClient.deleteNote(tenderId, n.id); setNotes(notes.filter((x) => x.id !== n.id)); } catch (err) { setError(err.message); }
  };
  return (
    <section data-testid="tender-notes" className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><StickyNote size={18} /> {t("Notes")}</h2>
        <button type="button" data-testid="open-notes" className={primary} onClick={() => setOpen(!open)}>{open ? t("Hide") : t("Show")}</button>
      </div>
      {open && (
        <div className="mt-3">
          <form onSubmit={add} className="grid gap-2 sm:grid-cols-[1fr_3fr_auto]">
            <input className={input} placeholder={t("Your name")} value={form.author} onChange={(e) => setForm({ ...form, author: e.target.value })} maxLength={120} />
            <input className={input} placeholder={t("Write a note for the team")} value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} maxLength={4000} />
            <button type="submit" className={primary}>{t("Add")}</button>
          </form>
          {error && <p className="mt-2 text-[13px] text-[#b42318]">{error}</p>}
          <ul className="mt-3 space-y-2">
            {notes.map((n) => (
              <li key={n.id} className="flex gap-2 rounded-lg bg-[#faf9f6] p-2.5 text-[13px] text-[#344054]">
                <div className="min-w-0 flex-1"><p className="whitespace-pre-line">{n.text}</p>
                  <p className="text-[11px] text-[#98a2b3]">{n.author || t("Team")} · {n.created_at ? new Date(n.created_at).toLocaleString() : ""}</p></div>
                <button type="button" aria-label={t("Remove")} onClick={() => remove(n)} className="text-[#b42318]"><Trash2 size={14} /></button>
              </li>
            ))}
            {!notes.length && <li className="text-[13px] text-[#667085]">{t("No notes yet.")}</li>}
          </ul>
        </div>
      )}
    </section>
  );
}

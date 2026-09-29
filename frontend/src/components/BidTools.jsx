import { useEffect, useState } from "react";
import { ShieldAlert, ShieldCheck, Layers, ListTodo, Vote, Trophy, Trash2, CheckCircle2, Circle } from "lucide-react";
import apiClient from "../api/client";
import { useT } from "../i18n";
import { DEPARTMENTS } from "./SettingsStage6";

/** Stage 6 — tender workspace tools: the eligibility result (and override),
 *  RFP parts with past suppliers, team tasks, department votes and the outcome. */

const input = "w-full min-w-0 rounded-lg border border-[#d0d5dd] px-3 py-2 text-[14px] outline-none focus:border-[#162A4C]";
const primary = "rounded-lg bg-[#162A4C] px-4 py-2 text-[14px] font-semibold text-white disabled:opacity-50";
/** Translate a backend template; string vars are translated too (comma-separated lists item by item). */
export const tx = (t, key, vars, fallback) => {
  if (!key) return fallback;
  const v = Object.fromEntries(Object.entries(vars || {}).map(([k, x]) =>
    [k, typeof x === "string" ? x.split(", ").map((p) => t(p)).join(t(", ")) : x]));
  return t(key, v);
};

export const LABEL = {
  PASS: "Met|check", FAIL: "Not met|check", UNCLEAR: "Unclear|check",
  APPROVE: "Approve|vote", REJECT: "Reject|vote", ABSTAIN: "Abstain|vote",
  SUBMITTED: "Submitted|outcome", WON: "Won|outcome", LOST: "Lost|outcome", NOT_SUBMITTED: "Not submitted|outcome",
};
const L = (t, v) => t(LABEL[v] || v);

const RESULT_STYLE = { PASS: "bg-[#e7f5ee] text-[#1f7a4d]", FAIL: "bg-[#fdf0f0] text-[#b42318]", UNCLEAR: "bg-[#f2f4f7] text-[#475467]" };

function Block({ icon: Icon, title, children, testid }) {
  return (
    <div data-testid={testid} className="rounded-xl border border-[#eef0f3] p-4">
      <h3 className="mb-3 flex items-center gap-2 text-[15px] font-bold text-[#101828]"><Icon size={17} /> {title}</h3>
      {children}
    </div>
  );
}

function Checks({ checks }) {
  const t = useT();
  return (
    <ul className="space-y-2">
      {checks.map((c) => (
        <li key={c.key} className="text-[13px] text-[#344054]">
          <span className={`me-2 rounded px-2 py-0.5 text-[11px] font-bold ${RESULT_STYLE[c.result] || ""}`}>{L(t, c.result)}</span>
          <b>{t(c.label)}:</b> {tx(t, c.detail_key, c.detail_vars, c.detail)}
          {c.evidence && <span className="block text-[12px] text-[#667085]">{c.evidence.file} · {t("page")} {c.evidence.page} — “{c.evidence.quote}”</span>}
        </li>
      ))}
    </ul>
  );
}

/** Shown on an INELIGIBLE tender: why, and "continue anyway". */
export function EligibilityBanner({ tenderId, onContinue }) {
  const t = useT();
  const [el, setEl] = useState(null);
  const [form, setForm] = useState({ by: "", reason: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => { apiClient.getEligibility(tenderId).then(setEl).catch((e) => setError(e.message)); }, [tenderId]);
  const go = async (e) => {
    e.preventDefault();
    if (!form.reason.trim()) { setError(t("Write why the team continues")); return; }
    setBusy(true); setError(null);
    try { await apiClient.overrideEligibility(tenderId, form); onContinue?.(); } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  return (
    <section data-testid="eligibility-banner" className="rounded-2xl border border-[#f5c6c6] bg-[#fdf6f6] p-5 sm:p-6">
      <h2 className="flex items-center gap-2 text-[17px] font-bold text-[#b42318]"><ShieldAlert size={19} /> {t("This tender does not fit the company")}</h2>
      <p className="mt-1 text-[13px] text-[#667085]">{t("The full analysis was stopped after the eligibility check. Review the reasons below.")}</p>
      {el?.checks?.length ? <div className="mt-3"><Checks checks={el.checks} /></div> : null}
      <form onSubmit={go} className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-[1fr_2fr_auto]">
        <input className={input} placeholder={t("Your name")} value={form.by} onChange={(e) => setForm({ ...form, by: e.target.value })} maxLength={120} />
        <input className={input} placeholder={t("Why continue anyway?")} value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} maxLength={1000} />
        <button type="submit" data-testid="continue-anyway" className={primary} disabled={busy}>{t("Continue anyway")}</button>
      </form>
      {error && <p className="mt-2 text-[13px] text-[#b42318]">{error}</p>}
    </section>
  );
}

function Sections({ data }) {
  const t = useT();
  if (!data) return null;
  if (!data.sections?.length) return <p className="text-[13px] text-[#667085]">{t("No parts found yet — process the tender first.")}</p>;
  return (
    <div className="space-y-3">
      <div className="max-h-[320px] overflow-auto">
        <table className="w-full text-start text-[13px]">
          <thead><tr className="text-[12px] text-[#667085]"><th className="py-1 text-start">{t("Part")}</th><th className="text-start">{t("Pages")}</th><th className="text-start">{t("Discipline")}</th></tr></thead>
          <tbody>
            {data.sections.map((s, i) => (
              <tr key={i} className="border-t border-[#f0ede6] align-top">
                <td className="py-1.5 pe-2"><b>{s.title}</b><span className="block text-[11px] text-[#98a2b3]">{s.document}</span></td>
                <td className="whitespace-nowrap pe-2">{s.page_from}–{s.page_to}</td>
                <td>{t(s.discipline)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div>
        <p className="mb-1 text-[13px] font-bold text-[#101828]">{t("Suggested suppliers from past tenders")}</p>
        <ul className="space-y-1 text-[13px] text-[#344054]">
          {data.disciplines.map((d) => (
            <li key={d.discipline}><b>{t(d.discipline)}</b> ({d.pages} {t("pages")}):{" "}
              {d.suppliers.length ? d.suppliers.map((s) => `${s.contractor}${s.selected ? ` ★${s.selected}` : ""}${s.avg_fit != null ? ` · ${s.avg_fit}%` : ""}`).join(" · ")
                : <span className="text-[#98a2b3]">{t("none recorded yet")}</span>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function Tasks({ tenderId, team }) {
  const t = useT();
  const [tasks, setTasks] = useState([]);
  const [form, setForm] = useState({ title: "", assignee: "", due_date: "" });
  const [error, setError] = useState(null);
  useEffect(() => { apiClient.listTasks(tenderId).then((d) => setTasks(Array.isArray(d) ? d : [])).catch(() => {}); }, [tenderId]);
  const add = async (e) => {
    e.preventDefault();
    if (!form.title.trim()) { setError(t("Enter a task")); return; }
    const member = team.find((m) => m.name === form.assignee);
    try {
      const task = await apiClient.addTask(tenderId, { ...form, department: member?.department || null });
      setTasks([...tasks, task]); setForm({ title: "", assignee: form.assignee, due_date: "" }); setError(null);
    } catch (err) { setError(err.message); }
  };
  const toggle = async (task) => {
    const upd = await apiClient.updateTask(tenderId, task.id, { status: task.status === "DONE" ? "OPEN" : "DONE" });
    setTasks(tasks.map((x) => (x.id === task.id ? upd : x)));
  };
  const remove = async (task) => { await apiClient.deleteTask(tenderId, task.id); setTasks(tasks.filter((x) => x.id !== task.id)); };
  return (
    <div>
      <ul className="mb-3 space-y-1">
        {tasks.map((x) => (
          <li key={x.id} className="flex items-center gap-2 text-[14px]">
            <button type="button" aria-label={x.status === "DONE" ? t("Mark open") : t("Mark done")} onClick={() => toggle(x)}>
              {x.status === "DONE" ? <CheckCircle2 size={17} className="text-[#1f7a4d]" /> : <Circle size={17} className="text-[#98a2b3]" />}
            </button>
            <span className={x.status === "DONE" ? "text-[#98a2b3] line-through" : ""}>{x.title}</span>
            <span className="text-[12px] text-[#667085]">{[x.assignee, x.due_date].filter(Boolean).join(" · ")}</span>
            <button type="button" aria-label={t("Remove")} onClick={() => remove(x)} className="ms-auto text-[#b42318]"><Trash2 size={14} /></button>
          </li>
        ))}
        {!tasks.length && <li className="text-[13px] text-[#667085]">{t("No tasks yet.")}</li>}
      </ul>
      <form onSubmit={add} className="grid gap-2 sm:grid-cols-2 xl:grid-cols-[2fr_1fr_1fr_auto]">
        <input className={input} placeholder={t("Task")} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} maxLength={300} />
        <select className={input} value={form.assignee} onChange={(e) => setForm({ ...form, assignee: e.target.value })} aria-label={t("Assignee")}>
          <option value="">{t("Assignee")}</option>
          {team.map((m) => <option key={m.id} value={m.name}>{m.name}</option>)}
        </select>
        <input type="date" className={input} value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} aria-label={t("Due date")} />
        <button type="submit" className={primary}>{t("Add")}</button>
      </form>
      {error && <p className="mt-2 text-[13px] text-[#b42318]">{error}</p>}
    </div>
  );
}

function Votes({ tenderId, team }) {
  const t = useT();
  const [data, setData] = useState(null);
  const [form, setForm] = useState({ member_name: "", department: DEPARTMENTS[0], vote: "APPROVE", comment: "" });
  const [error, setError] = useState(null);
  useEffect(() => { apiClient.getVotes(tenderId).then(setData).catch(() => {}); }, [tenderId]);
  const pick = (name) => {
    const m = team.find((x) => x.name === name);
    setForm({ ...form, member_name: name, department: m?.department || form.department });
  };
  const save = async (e) => {
    e.preventDefault();
    if (!form.member_name.trim()) { setError(t("Choose who is voting")); return; }
    try { setData(await apiClient.putVote(tenderId, form)); setError(null); } catch (err) { setError(err.message); }
  };
  const o = data?.summary?.overall;
  return (
    <div>
      {o && o.total > 0 && (
        <div className="mb-3">
          <p data-testid="votes-overall" className="text-[14px] text-[#101828]">
            <b>{o.approve_pct != null ? `${o.approve_pct}%` : "—"}</b> {t("approve")} · {t("{a} approve, {r} reject, {x} abstain", { a: o.approve, r: o.reject, x: o.abstain })}
          </p>
          <ul className="mt-1 text-[13px] text-[#475467]">
            {data.summary.by_department.map((d) => (
              <li key={d.department}>{t(d.department)}: {d.approve_pct != null ? `${d.approve_pct}%` : "—"} ({d.approve}/{d.approve + d.reject})</li>
            ))}
          </ul>
          <ul className="mt-2 space-y-0.5 text-[12px] text-[#667085]">
            {data.votes.map((v) => <li key={v.member_name}>{v.member_name} ({t(v.department)}): {L(t, v.vote)}{v.comment ? ` — ${v.comment}` : ""}</li>)}
          </ul>
        </div>
      )}
      <form onSubmit={save} className="grid gap-2 sm:grid-cols-2 xl:grid-cols-[1fr_1fr_1fr_2fr_auto]">
        {team.length ? (
          <select className={input} value={form.member_name} onChange={(e) => pick(e.target.value)} aria-label={t("Member")}>
            <option value="">{t("Member")}</option>
            {team.map((m) => <option key={m.id} value={m.name}>{m.name}</option>)}
          </select>
        ) : <input className={input} placeholder={t("Member")} value={form.member_name} onChange={(e) => setForm({ ...form, member_name: e.target.value })} />}
        <select className={input} value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} aria-label={t("Department")}>
          {DEPARTMENTS.map((d) => <option key={d} value={d}>{t(d)}</option>)}
        </select>
        <select className={input} value={form.vote} onChange={(e) => setForm({ ...form, vote: e.target.value })} aria-label={t("Vote")}>
          {["APPROVE", "REJECT", "ABSTAIN"].map((v) => <option key={v} value={v}>{L(t, v)}</option>)}
        </select>
        <input className={input} placeholder={t("Comment (optional)")} value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} maxLength={1000} />
        <button type="submit" className={primary}>{t("Save vote")}</button>
      </form>
      {error && <p className="mt-2 text-[13px] text-[#b42318]">{error}</p>}
    </div>
  );
}

const OUTCOMES = ["SUBMITTED", "WON", "LOST", "NOT_SUBMITTED"];

function Outcome({ tenderId, initial }) {
  const t = useT();
  const [value, setValue] = useState(initial || "");
  const [msg, setMsg] = useState(null);
  const save = async (v) => {
    setValue(v);
    try { await apiClient.setOutcome(tenderId, v || null); setMsg(t("Saved")); } catch (err) { setMsg(err.message); }
  };
  return (
    <div className="flex flex-wrap items-center gap-2">
      <select className={`${input} w-auto`} value={value} onChange={(e) => save(e.target.value)} aria-label={t("Outcome")}>
        <option value="">{t("Not set")}</option>
        {OUTCOMES.map((o) => <option key={o} value={o}>{L(t, o)}</option>)}
      </select>
      <span className="text-[12px] text-[#667085]">{t("Won/lost results feed the “similar past tenders” part of the score.")}</span>
      {msg && <span className="text-[12px] text-[#1f7a4d]">{msg}</span>}
    </div>
  );
}

/** Loaded on demand (the workspace itself stays fast). */
export default function BidTools({ tenderId, outcome }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [team, setTeam] = useState([]);
  const [sections, setSections] = useState(null);
  const [elig, setElig] = useState(null);
  useEffect(() => {
    if (!open) return;
    apiClient.listTeam().then((d) => setTeam(Array.isArray(d) ? d : [])).catch(() => {});
    apiClient.getSections(tenderId).then(setSections).catch(() => setSections({ sections: [], disciplines: [] }));
    apiClient.getEligibility(tenderId).then(setElig).catch(() => {});
  }, [open, tenderId]);
  return (
    <section data-testid="bid-tools" className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><Layers size={18} /> {t("Tender team & tools")}</h2>
        <button type="button" data-testid="open-bid-tools" onClick={() => setOpen(!open)} className={primary}>{open ? t("Hide") : t("Open")}</button>
      </div>
      {open && (
        <div className="mt-4 space-y-4">
          {elig?.status && (elig.status !== "INELIGIBLE" || elig.override_by) && (
            <Block icon={ShieldCheck} title={t("Eligibility check")} testid="eligibility-checks">
              {elig.status === "SKIPPED" || !elig.checks?.length
                ? <p className="text-[13px] text-[#667085]">{t("Not checked — fill Company capabilities in Settings.")}</p>
                : <Checks checks={elig.checks} />}
              {elig.override_by && <p className="mt-2 text-[12px] text-[#8a6a22]">{t("Continued by {by}: {reason}", { by: elig.override_by, reason: elig.override_reason || "" })}</p>}
            </Block>
          )}
          <Block icon={Layers} title={t("RFP parts and suggested suppliers")} testid="rfp-sections"><Sections data={sections} /></Block>
          <Block icon={ListTodo} title={t("Team tasks")} testid="tender-tasks"><Tasks tenderId={tenderId} team={team} /></Block>
          <Block icon={Vote} title={t("Department votes")} testid="department-votes"><Votes tenderId={tenderId} team={team} /></Block>
          <Block icon={Trophy} title={t("Tender outcome")} testid="tender-outcome"><Outcome tenderId={tenderId} initial={outcome} /></Block>
        </div>
      )}
    </section>
  );
}

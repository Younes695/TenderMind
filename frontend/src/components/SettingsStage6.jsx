import { useEffect, useState } from "react";
import { ShieldCheck, Users, Scale, Trash2 } from "lucide-react";
import apiClient from "../api/client";
import { useT } from "../i18n";
import { useAccountType } from "../account";

/** Stage 6 settings cards: company capabilities (eligibility gate), the tender
 *  team (one shared login, named members) and the Go/No-Go factor weights. */

export const WORK_TYPES = ["substation", "overhead line", "cable", "distribution", "generation", "renewables", "other"];
export const COUNTRIES = ["Saudi Arabia", "Egypt", "United Arab Emirates", "Qatar", "Kuwait", "Oman", "Bahrain"];
export const DEPARTMENTS = ["Engineering", "Procurement", "Finance", "Legal", "Commercial", "Projects", "HSE", "Management"];

const input = "w-full rounded-lg border border-[#d0d5dd] px-3 py-2 text-[14px] outline-none focus:border-[#162A4C]";
const primary = "rounded-lg bg-[#162A4C] px-4 py-2 text-[14px] font-semibold text-white disabled:opacity-50";

function Shell({ icon: Icon, title, hint, children, testid }) {
  return (
    <section data-testid={testid} className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
      <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><Icon size={18} /> {title}</h2>
      {hint && <p className="mb-4 mt-1 text-[13px] text-[#667085]">{hint}</p>}
      {children}
    </section>
  );
}

function Msg({ msg }) {
  if (!msg) return null;
  const ok = msg.startsWith("ok:");
  return <p className={`mt-3 text-[13px] ${ok ? "text-[#1f7a4d]" : "text-[#b42318]"}`}>{msg.slice(msg.indexOf(":") + 1)}</p>;
}

function Toggles({ options, value, onChange, label }) {
  const t = useT();
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => {
        const on = value.includes(o);
        return (
          <button key={o} type="button" aria-pressed={on} onClick={() => onChange(on ? value.filter((x) => x !== o) : [...value, o])}
            className={`rounded-full border px-3 py-1.5 text-[13px] font-semibold ${on ? "border-[#162A4C] bg-[#162A4C] text-white" : "border-[#d0d5dd] bg-white text-[#344054]"}`}
            aria-label={`${label}: ${t(o)}`}>{t(o)}</button>
        );
      })}
    </div>
  );
}

const lines = (s) => s.split("\n").map((x) => x.trim()).filter(Boolean);

export function CapabilityCard() {
  const accountType = useAccountType();
  const t = useT();
  const [cap, setCap] = useState(null);
  const [text, setText] = useState({ registrations: "", certifications: "" });
  const [msg, setMsg] = useState(null);
  useEffect(() => {
    apiClient.getCapability().then((c) => {
      setCap(c);
      setText({ registrations: (c.registrations || []).join("\n"), certifications: (c.certifications || []).join("\n") });
    }).catch(() => setCap({ work_types: [], countries: [] }));
  }, []);
  if (!cap) return null;
  const num = (k) => (
    <label className="text-[13px] text-[#344054]">{t({ max_kv: "Highest voltage you work on (kV)", years_experience: "Years of experience", annual_turnover: "Annual turnover" }[k])}
      <input type="number" min="0" className={input} value={cap[k] ?? ""} onChange={(e) => setCap({ ...cap, [k]: e.target.value })} />
    </label>
  );
  const save = async (e) => {
    e.preventDefault();
    try {
      const saved = await apiClient.saveCapability({ ...cap, registrations: lines(text.registrations), certifications: lines(text.certifications) });
      setCap(saved);
      setMsg(`ok:${t("Saved")}`);
    } catch (err) { setMsg(`err:${err.message}`); }
  };
  return (
    <Shell icon={ShieldCheck} testid="capability-card" title={accountType === "individual" ? t("My capabilities & certificates") : t("Company capabilities")}
      hint={t("Each new tender is checked against these before the full analysis. Leave empty to skip the check.")}>
      <form onSubmit={save} className="space-y-4">
        <div><p className="mb-2 text-[13px] font-semibold text-[#344054]">{t("Types of work")}</p>
          <Toggles label={t("Types of work")} options={WORK_TYPES} value={cap.work_types || []} onChange={(v) => setCap({ ...cap, work_types: v })} /></div>
        <div><p className="mb-2 text-[13px] font-semibold text-[#344054]">{t("Countries you work in")}</p>
          <Toggles label={t("Countries you work in")} options={COUNTRIES} value={cap.countries || []} onChange={(v) => setCap({ ...cap, countries: v })} /></div>
        <div className="grid gap-3 sm:grid-cols-3">
          {num("max_kv")}{num("years_experience")}
          <div className="flex gap-2"><div className="min-w-0 flex-1">{num("annual_turnover")}</div>
            <label className="w-20 shrink-0 text-[13px] text-[#344054]">{t("Currency")}
              <input className={input} maxLength={3} value={cap.turnover_currency || ""} placeholder="SAR" onChange={(e) => setCap({ ...cap, turnover_currency: e.target.value })} />
            </label>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-[13px] text-[#344054]">{t("Registrations / classifications (one per line)")}
            <textarea rows={3} className={input} value={text.registrations} placeholder="SEC approved contractor" onChange={(e) => setText({ ...text, registrations: e.target.value })} />
          </label>
          <label className="text-[13px] text-[#344054]">{t("Certifications (one per line)")}
            <textarea rows={3} className={input} value={text.certifications} placeholder="ISO 9001" onChange={(e) => setText({ ...text, certifications: e.target.value })} />
          </label>
        </div>
        <button type="submit" className={primary}>{t("Save")}</button>
      </form>
      <Msg msg={msg} />
    </Shell>
  );
}

export function TeamCard() {
  const t = useT();
  const [team, setTeam] = useState([]);
  const [form, setForm] = useState({ name: "", department: DEPARTMENTS[0], role: "" });
  const [msg, setMsg] = useState(null);
  useEffect(() => { apiClient.listTeam().then((d) => setTeam(Array.isArray(d) ? d : [])).catch(() => {}); }, []);
  const add = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { setMsg(`err:${t("Enter a name")}`); return; }
    try { const m = await apiClient.addTeamMember(form); setTeam([...team, m]); setForm({ ...form, name: "", role: "" }); setMsg(null); }
    catch (err) { setMsg(`err:${err.message}`); }
  };
  const remove = async (id) => {
    try { await apiClient.deleteTeamMember(id); setTeam(team.filter((m) => m.id !== id)); } catch (err) { setMsg(`err:${err.message}`); }
  };
  return (
    <Shell icon={Users} testid="team-card" title={t("Tender team")}
      hint={t("Everyone signs in with the company account. Add the people here so tasks and votes carry their names.")}>
      <ul className="mb-3 divide-y divide-[#f0ede6]">
        {team.map((m) => (
          <li key={m.id} className="flex items-center justify-between py-2 text-[14px]">
            <span><b>{m.name}</b> · {t(m.department || "")}{m.role ? ` · ${m.role}` : ""}</span>
            <button type="button" aria-label={t("Remove")} onClick={() => remove(m.id)} className="text-[#b42318]"><Trash2 size={15} /></button>
          </li>
        ))}
        {!team.length && <li className="py-2 text-[13px] text-[#667085]">{t("No team members yet.")}</li>}
      </ul>
      <form onSubmit={add} className="grid gap-2 sm:grid-cols-4">
        <input className={input} placeholder={t("Name")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={120} />
        <select className={input} value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}>
          {DEPARTMENTS.map((d) => <option key={d} value={d}>{t(d)}</option>)}
        </select>
        <input className={input} placeholder={t("Role (optional)")} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} maxLength={120} />
        <button type="submit" className={primary}>{t("Add")}</button>
      </form>
      <Msg msg={msg} />
    </Shell>
  );
}

const FACTORS = [["fit", "Company fit"], ["history", "Similar past tenders"], ["partners", "Past partners"], ["votes", "Department votes"]];

export function WeightsCard() {
  const t = useT();
  const [w, setW] = useState(null);
  const [msg, setMsg] = useState(null);
  useEffect(() => { apiClient.getScoreWeights().then(setW).catch(() => setW({ fit: 40, history: 20, partners: 15, votes: 25 })); }, []);
  if (!w) return null;
  const total = FACTORS.reduce((s, [k]) => s + (Number(w[k]) || 0), 0);
  const save = async (e) => {
    e.preventDefault();
    try { setW(await apiClient.saveScoreWeights(w)); setMsg(`ok:${t("Saved")}`); } catch (err) { setMsg(`err:${err.message}`); }
  };
  return (
    <Shell icon={Scale} testid="weights-card" title={t("Go/No-Go score weights")}
      hint={t("How much each factor counts in the score. A factor without data is left out and the others are rescaled.")}>
      <form onSubmit={save} className="grid gap-3 sm:grid-cols-4">
        {FACTORS.map(([k, label]) => (
          <label key={k} className="text-[13px] text-[#344054]">{t(label)}
            <input type="number" min="0" max="100" className={input} value={w[k]} onChange={(e) => setW({ ...w, [k]: e.target.value })} />
          </label>
        ))}
        <p className="text-[12px] text-[#667085] sm:col-span-3">{t("Total: {n}", { n: total })}</p>
        <button type="submit" className={primary} disabled={total <= 0}>{t("Save")}</button>
      </form>
      <Msg msg={msg} />
    </Shell>
  );
}

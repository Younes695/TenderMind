import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlarmClock, Gavel, ShieldAlert, History, ArrowUpRight } from "lucide-react";
import apiClient from "../api/client";
import { useT } from "../i18n";
import { tx } from "./BidTools";
import { STAGE_LABEL } from "./TenderIntel";

/** Stage 8 — "Needs attention now" for the Tender Manager, and the reminders list. */

const PRI = { HIGH: "bg-[#fdf0f0] text-[#b42318]", MEDIUM: "bg-[#fdf4de] text-[#8a6a22]", LOW: "bg-[#f2f4f7] text-[#475467]" };
const BAND = { GO: ["Go|band", "bg-[#1f7a4d]"], REVIEW: ["Review|band", "bg-[#a98238]"], NO_GO: ["No-Go|band", "bg-[#b42318]"] };

export function RemindersList({ items, testid = "reminders" }) {
  const t = useT();
  if (!items?.length) return null;
  return (
    <ul data-testid={testid} className="space-y-1.5">
      {items.map((r, i) => (
        <li key={i} className="flex flex-wrap items-center gap-2 text-[13px] text-[#344054]">
          <span className={`rounded px-2 py-0.5 text-[11px] font-bold ${PRI[r.priority]}`}>{t(r.priority)}</span>
          <Link to={`/tenders/${encodeURIComponent(r.tender_id)}`} className="font-semibold text-[#162A4C] underline">{r.tender_id}</Link>
          <span>{tx(t, r.key, r.vars)}</span>
          {r.assignee && <span className="text-[12px] text-[#667085]">— {r.assignee}</span>}
        </li>
      ))}
    </ul>
  );
}

function Box({ icon: Icon, title, count, children, testid }) {
  return (
    <div data-testid={testid} className="rounded-2xl border border-[#e5e1d9] bg-white p-4">
      <p className="mb-2 flex items-center gap-2 text-[14px] font-bold text-[#102b50]"><Icon size={16} /> {title}
        {count != null && <span className="rounded-full bg-[#162A4C] px-2 text-[11px] text-white">{count}</span>}</p>
      {children}
    </div>
  );
}

export default function AttentionPanel({ data }) {
  const t = useT();
  const [own, setOwn] = useState(null);
  useEffect(() => {
    if (data === undefined) apiClient.getAttention().then((x) => x && x.stages && setOwn(x)).catch(() => {});
  }, [data]);
  const d = data === undefined ? own : data;
  if (!d) return null;
  const empty = <p className="text-[13px] text-[#667085]">{t("Nothing here right now.")}</p>;
  return (
    <section data-testid="attention" className="mb-5">
      <h2 className="mb-3 text-[18px] font-black text-[#102b50]">{t("Needs attention now")}</h2>
      <div className="grid gap-4 lg:grid-cols-2">
        <Box icon={AlarmClock} title={t("Deadlines and overdue tasks")} count={d.reminders.length} testid="attention-reminders">
          {d.reminders.length ? <RemindersList items={d.reminders.slice(0, 8)} /> : empty}
        </Box>
        <Box icon={Gavel} title={t("Awaiting a Go/No-Go decision")} count={d.awaiting_decision.length} testid="attention-awaiting">
          {d.awaiting_decision.length ? (
            <ul className="space-y-1.5">
              {d.awaiting_decision.slice(0, 8).map((x) => {
                const [label, bg] = BAND[x.band] || ["—", "bg-[#98a2b3]"];
                return (
                  <li key={x.id} className="flex items-center gap-2 text-[13px] text-[#344054]">
                    <span className={`w-12 rounded px-1.5 py-0.5 text-center text-[11px] font-bold text-white ${bg}`}>{x.score ?? "—"}</span>
                    <Link to={`/tenders/${encodeURIComponent(x.id)}`} className="min-w-0 flex-1 truncate font-semibold text-[#162A4C]">{x.title || x.id}</Link>
                    <span className="text-[12px]">{t(label)}</span>
                    {x.stage && <span className="text-[12px] text-[#667085]">{t(STAGE_LABEL[x.stage] || x.stage)}</span>}
                    {x.deadline && <span className="text-[12px] text-[#667085]">{x.deadline}</span>}
                    <ArrowUpRight size={13} className="text-[#98a2b3]" />
                  </li>
                );
              })}
            </ul>
          ) : empty}
        </Box>
        {d.blocked.length > 0 && (
          <Box icon={ShieldAlert} title={t("Stopped by the eligibility check")} count={d.blocked.length} testid="attention-blocked">
            <ul className="space-y-1 text-[13px]">{d.blocked.map((x) => <li key={x.id}><Link className="text-[#162A4C] underline" to={`/tenders/${encodeURIComponent(x.id)}`}>{x.title || x.id}</Link></li>)}</ul>
          </Box>
        )}
        {d.client_history.length > 0 && (
          <Box icon={History} title={t("Clients you worked with before")} count={d.client_history.length} testid="attention-clients">
            <ul className="space-y-1 text-[13px]">{d.client_history.map((x) => <li key={x.id}><Link className="text-[#162A4C] underline" to={`/tenders/${encodeURIComponent(x.id)}`}>{x.title || x.id}</Link></li>)}</ul>
          </Box>
        )}
      </div>
      <p className="mt-3 flex flex-wrap gap-2 text-[12px] text-[#667085]">
        {Object.entries(d.stages).map(([k, v]) => <span key={k} className="rounded-full bg-white px-2.5 py-1 ring-1 ring-[#e5e1d9]">{t(STAGE_LABEL[k] || `${k}|stage`)}: {v}</span>)}
      </p>
    </section>
  );
}

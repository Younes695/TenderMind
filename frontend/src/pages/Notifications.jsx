import { useEffect, useState } from "react";
import { Bell, ListTodo } from "lucide-react";
import { Link } from "react-router-dom";
import apiClient from "../api/client";
import IssueCard from "../components/IssueCard";
import { RemindersList } from "../components/Attention";
import { useT } from "../i18n";

/** Open review items across the account's tenders: missing, unreadable or
 *  unsupported files, referenced documents not in the package, and mandatory
 *  requirements with no company evidence. */
export default function Notifications() {
  const t = useT();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [groups, setGroups] = useState([]);
  const [reminders, setReminders] = useState([]);

  const load = () => apiClient.getNotifications().then(setData).catch((e) => setError(e.message));
  useEffect(() => {
    load();
    apiClient.getTaskGroups().then((g) => setGroups(Array.isArray(g) ? g : [])).catch(() => {});
    apiClient.getReminders().then((r) => setReminders(Array.isArray(r) ? r : [])).catch(() => {});
  }, []);

  const onChange = (updated) => {
    setData((d) => ({ ...d, notifications: d.notifications.map((n) => (n.id === updated.id ? updated : n)) }));
    window.dispatchEvent(new Event("tm:notifications-changed"));
  };

  if (error) return <div data-testid="error-banner" className="m-8 rounded-xl border border-[#f5c6c6] bg-[#fdf0f0] p-4 text-[#a33a3a]">{error}</div>;
  if (!data) return <div className="p-8">{t("Loading notifications…")}</div>;
  const open = data.notifications.filter((n) => n.status === "OPEN").length;

  return (
    <div className="mx-auto max-w-[1100px] space-y-4 p-4 sm:p-6 lg:p-8">
      <div>
        <h1 className="flex items-center gap-2 text-[24px] font-black text-[#101828]"><Bell size={22} /> {t("Needs review")}</h1>
        <p className="mt-1 text-[14px] text-[#667085]">
          {t("Things missing or unreadable in your tenders. Check each one and mark it reviewed.")} {open} {t("open")}.
        </p>
      </div>
      {reminders.length > 0 && (
        <section className="rounded-2xl border border-[#f5c6c6] bg-[#fffafa] p-5">
          <h2 className="mb-2 text-[16px] font-bold text-[#b42318]">{t("Deadlines and overdue tasks")}</h2>
          <RemindersList items={reminders} testid="notification-reminders" />
        </section>
      )}
      {groups.length > 0 && (
        <section data-testid="task-groups" className="rounded-2xl border border-[#c5d3e6] bg-[#f4f7fb] p-5">
          <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#162A4C]"><ListTodo size={18} /> {t("Similar tasks — do them once")}</h2>
          <ul className="mt-2 space-y-2">
            {groups.map((g) => (
              <li key={g.title} className="text-[14px] text-[#344054]">
                <b>{t("{n} similar tasks in {m} tenders", { n: g.count, m: g.tenders.length })}:</b> {g.title}
                <span className="block text-[12px] text-[#667085]">
                  {g.tasks.map((x, i) => (
                    <span key={i}>{i > 0 && " · "}<Link className="underline" to={`/tenders/${encodeURIComponent(x.tender_id)}`}>{x.tender_id}</Link>{x.assignee ? ` (${x.assignee})` : ""}</span>
                  ))}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {data.notifications.length === 0 ? (
        <div data-testid="empty-state" className="rounded-xl border border-[#e8e4dc] bg-white p-6 text-[14px] text-[#667085]">
          {t("Nothing needs review right now.")}
        </div>
      ) : (
        <div className="space-y-3">
          {data.notifications.map((n) => <IssueCard key={n.id} issue={n} showTender onChange={onChange} />)}
        </div>
      )}
    </div>
  );
}

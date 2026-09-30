import { useEffect, useState } from "react";
import { Settings as SettingsIcon, Building2, User, KeyRound, Languages, Moon, Sun, Monitor, Crown, LifeBuoy, Check, UserRound, Inbox } from "lucide-react";
import apiClient from "../api/client";
import { usePrefs } from "../i18n";
import { useAccountType, setAccountType } from "../account";
import { CapabilityCard, TeamCard, WeightsCard } from "../components/SettingsStage6";

const PLANS = [
  { id: "Starter", features: ["A few tenders a month", "Requirement extraction with page references", "Missing-item alerts and Q&A"] },
  { id: "Professional", features: ["More tenders a month", "Bid decision with company evidence", "Subcontractor RFQ comparison", "Unlimited team members"] },
  { id: "Enterprise", features: ["Runs inside your company — documents never leave", "Custom limits and integrations", "Dedicated support"] },
];

function Card({ icon: Icon, title, children }) {
  return (
    <section className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
      <h2 className="mb-4 flex items-center gap-2 text-[16px] font-bold text-[#101828]"><Icon size={18} /> {title}</h2>
      {children}
    </section>
  );
}

function Choice({ active, onClick, icon: Icon, label, testid }) {
  return (
    <button type="button" data-testid={testid} onClick={onClick} aria-pressed={active}
      className={`flex items-center gap-2 rounded-xl border px-4 py-2.5 text-[14px] font-semibold ${active ? "border-[#162A4C] bg-[#162A4C] text-white" : "border-[#d0d5dd] bg-white text-[#344054]"}`}>
      {Icon && <Icon size={16} />} {label} {active && <Check size={14} />}
    </button>
  );
}

function Notice({ msg }) {
  if (!msg) return null;
  const ok = msg.startsWith("ok:");
  return <p className={`mt-3 text-[13px] ${ok ? "text-[#1f7a4d]" : "text-[#b42318]"}`}>{msg.slice(msg.indexOf(":") + 1)}</p>;
}

/** Requests sent from the public "Book a demo" form. */
function DemoRequests() {
  const { t } = usePrefs();
  const [rows, setRows] = useState(null);
  useEffect(() => { apiClient.listDemoRequests().then((d) => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([])); }, []);
  return (
    <Card icon={Inbox} title={t("Demo requests from the website")}>
      {!rows ? null : !rows.length ? <p className="text-[13px] text-[#667085]">{t("No requests yet.")}</p> : (
        <ul data-testid="demo-requests" className="divide-y divide-[#f0ede6] text-[13px]">
          {rows.map((r) => (
            <li key={r.id} className="py-2">
              <b className="text-[#101828]">{r.name}</b> · <a href={`mailto:${r.email}`} className="text-[#162A4C] underline">{r.email}</a>
              {r.company ? ` · ${r.company}` : ""}{r.country ? ` · ${t(r.country)}` : ""}
              <span className="ms-2 rounded bg-[#f2f4f7] px-1.5 text-[11px]">{r.topic || "demo"}</span>
              <span className="block text-[12px] text-[#667085]">{new Date(r.created_at).toLocaleString()}{r.message ? ` — ${r.message}` : ""}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export default function Settings() {
  const { lang, setLang, theme, setTheme, t } = usePrefs();
  const accountType = useAccountType();
  const [typeMsg, setTypeMsg] = useState(null);
  const individual = accountType === "individual";
  const [me, setMe] = useState(null);
  const [name, setName] = useState("");
  const [nameMsg, setNameMsg] = useState(null);
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const [pwMsg, setPwMsg] = useState(null);
  const [planMsg, setPlanMsg] = useState(null);
  const [problem, setProblem] = useState("");
  const [problemMsg, setProblemMsg] = useState(null);
  const [reports, setReports] = useState([]);
  const [company, setCompany] = useState({});
  const [companyMsg, setCompanyMsg] = useState(null);

  useEffect(() => {
    apiClient.getCurrentUser().then((u) => { setMe(u); setName(u?.name || ""); }).catch(() => {});
    apiClient.listFeedback().then((d) => setReports(d?.items || [])).catch(() => {});
    apiClient.getCompanyProfile().then((p) => setCompany(p || {})).catch(() => {});
  }, []);

  const saveCompany = async (e) => {
    e.preventDefault();
    try { setCompany(await apiClient.saveCompanyProfile(company)); setCompanyMsg(`ok:${t("Saved")}`); }
    catch (err) { setCompanyMsg(`err:${err.message}`); }
  };

  const saveName = async (e) => {
    e.preventDefault();
    try { const u = await apiClient.updateProfile({ name }); setMe(u); setNameMsg(`ok:${t("Saved")}`); }
    catch (err) { setNameMsg(`err:${err.message}`); }
  };
  const savePassword = async (e) => {
    e.preventDefault();
    if (pw.new_password !== pw.confirm) { setPwMsg(`err:${t("The new passwords do not match")}`); return; }
    try {
      await apiClient.changePassword({ current_password: pw.current_password, new_password: pw.new_password });
      setPw({ current_password: "", new_password: "", confirm: "" });
      setPwMsg(`ok:${t("Password changed")}`);
    } catch (err) { setPwMsg(`err:${err.message}`); }
  };
  const requestPlan = async (plan) => {
    try { await apiClient.sendFeedback({ kind: "upgrade", plan }); setPlanMsg(`ok:${t("Thanks — our team will contact you about the {plan} plan.", { plan })}`); }
    catch (err) { setPlanMsg(`err:${err.message}`); }
  };
  const sendProblem = async (e) => {
    e.preventDefault();
    try {
      await apiClient.sendFeedback({ kind: "problem", message: problem, page: window.location.pathname });
      setProblem("");
      setProblemMsg(`ok:${t("Received — we will follow up and fix it.")}`);
      apiClient.listFeedback().then((d) => setReports(d?.items || [])).catch(() => {});
    } catch (err) { setProblemMsg(`err:${err.message}`); }
  };

  const input = "w-full rounded-lg border border-[#d0d5dd] px-3 py-2 text-[14px] outline-none focus:border-[#162A4C]";
  const primary = "rounded-lg bg-[#162A4C] px-4 py-2 text-[14px] font-semibold text-white disabled:opacity-50";

  return (
    <div className="mx-auto max-w-[900px] space-y-5 p-4 sm:p-6 lg:p-8">
      <h1 className="flex items-center gap-2 text-[24px] font-black text-[#101828]"><SettingsIcon size={22} /> {t("Settings")}</h1>

      <Card icon={Languages} title={t("Language")}>
        <div className="flex flex-wrap gap-2">
          <Choice testid="lang-en" active={lang === "en"} onClick={() => setLang("en")} label="English" />
          <Choice testid="lang-ar" active={lang === "ar"} onClick={() => setLang("ar")} label="العربية" />
        </div>
      </Card>

      <Card icon={Moon} title={t("Appearance")}>
        <div className="flex flex-wrap gap-2">
          <Choice testid="theme-light" active={theme === "light"} onClick={() => setTheme("light")} icon={Sun} label={t("Light")} />
          <Choice testid="theme-dark" active={theme === "dark"} onClick={() => setTheme("dark")} icon={Moon} label={t("Dark")} />
          <Choice testid="theme-system" active={theme === "system"} onClick={() => setTheme("system")} icon={Monitor} label={t("Same as device")} />
        </div>
      </Card>

      <Card icon={User} title={t("Profile")}>
        <form onSubmit={saveName} className="grid gap-3 sm:grid-cols-2">
          <label className="text-[13px] text-[#344054]">{t("Name")}
            <input className={input} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
          </label>
          <label className="text-[13px] text-[#344054]">{t("Email")}
            <input className={`${input} bg-[#f2f4f7]`} value={me?.email || ""} readOnly />
          </label>
          <div><button type="submit" className={primary} disabled={!name.trim()}>{t("Save")}</button></div>
        </form>
        <Notice msg={nameMsg} />
      </Card>

      <Card icon={Building2} title={t("Account type")}>
        <div data-testid="account-type-setting" className="flex flex-wrap gap-2">
          <Choice active={!individual} onClick={async () => { await setAccountType("company"); setTypeMsg(`ok:${t("Saved")}`); }}
            icon={Building2} label={t("Company")} testid="account-company" />
          <Choice active={individual} onClick={async () => { await setAccountType("individual"); setTypeMsg(`ok:${t("Saved")}`); }}
            icon={UserRound} label={t("Individual professional")} testid="account-individual" />
        </div>
        <p className="mt-2 text-[12px] text-[#667085]">{individual
          ? t("Individual: your own profile, certificates and tender history. Team members, department votes and approvals are hidden.")
          : t("Company: a tender team with members, department votes and approvals.")}</p>
        <Notice msg={typeMsg} />
      </Card>

      <Card icon={Building2} title={individual ? t("My profile") : t("Company profile")}>
        <form onSubmit={saveCompany} data-testid="company-profile" className="grid gap-3 sm:grid-cols-2">
          {[["name", individual ? "Name / trading name" : "Company name"], ["contact_name", "Contact person"], ["contact_title", "Job title"], ["email", "Email"],
            ["phone", "Phone"], ["website", "Website"], ["address", "Address"]].map(([k, label]) => (
            <label key={k} className="text-[13px] text-[#344054]">{t(label)}
              <input className={input} value={company[k] || ""} onChange={(e) => setCompany({ ...company, [k]: e.target.value })} maxLength={k === "address" ? 400 : 200} />
            </label>
          ))}
          <label className="text-[13px] text-[#344054] sm:col-span-2">{t("Short introduction (used in bid emails)")}
            <textarea className={input} rows={3} maxLength={2000} value={company.intro || ""} onChange={(e) => setCompany({ ...company, intro: e.target.value })} />
          </label>
          <div><button type="submit" className={primary}>{t("Save")}</button></div>
        </form>
        <Notice msg={companyMsg} />
      </Card>

      <CapabilityCard />
      {!individual && <TeamCard />}
      <WeightsCard />
      {(me?.is_admin || me?.auth_disabled) && <DemoRequests />}

      <Card icon={KeyRound} title={t("Change password")}>
        <form onSubmit={savePassword} className="grid gap-3 sm:grid-cols-3">
          {[["current_password", "Current password"], ["new_password", "New password"], ["confirm", "Repeat new password"]].map(([k, label]) => (
            <label key={k} className="text-[13px] text-[#344054]">{t(label)}
              <input type="password" autoComplete={k === "current_password" ? "current-password" : "new-password"} className={input}
                value={pw[k]} onChange={(e) => setPw({ ...pw, [k]: e.target.value })} />
            </label>
          ))}
          <div><button type="submit" className={primary} disabled={!pw.new_password}>{t("Change password")}</button></div>
        </form>
        <p className="mt-2 text-[12px] text-[#667085]">{t("At least 8 characters, with letters and numbers. Google / Microsoft accounts are managed by that provider.")}</p>
        <Notice msg={pwMsg} />
      </Card>

      <Card icon={Crown} title={t("Plan")}>
        <p className="mb-3 text-[14px] text-[#344054]">{t("Current plan")}: <b>{t("Free trial")}</b></p>
        <div className="grid gap-3 md:grid-cols-3">
          {PLANS.map((p) => (
            <div key={p.id} className="flex flex-col rounded-xl border border-[#e8e4dc] p-4">
              <p className="text-[15px] font-bold text-[#101828]">{p.id}</p>
              <ul className="mt-2 flex-1 space-y-1 text-[13px] text-[#475467]">
                {p.features.map((f) => <li key={f} className="flex gap-1.5"><Check size={14} className="mt-0.5 shrink-0 text-[#1f7a4d]" /> {t(f)}</li>)}
              </ul>
              <button type="button" data-testid={`upgrade-${p.id}`} onClick={() => requestPlan(p.id)} className={`${primary} mt-3`}>
                {t("Contact us to upgrade")}
              </button>
            </div>
          ))}
        </div>
        <Notice msg={planMsg} />
      </Card>

      <Card icon={LifeBuoy} title={t("Report a problem")}>
        <form onSubmit={sendProblem}>
          <textarea data-testid="problem-text" value={problem} onChange={(e) => setProblem(e.target.value)} rows={3} maxLength={4000}
            placeholder={t("Tell us what went wrong — which tender, which page, what you expected.")} className={input} />
          <button type="submit" className={`${primary} mt-2`} disabled={!problem.trim()}>{t("Send")}</button>
        </form>
        <Notice msg={problemMsg} />
        {reports.filter((r) => r.kind === "problem").length > 0 && (
          <ul className="mt-4 space-y-2">
            {reports.filter((r) => r.kind === "problem").map((r) => (
              <li key={r.id} className="rounded-lg bg-[#faf9f6] p-3 text-[13px] text-[#344054]">
                <span className="me-2 rounded bg-[#eef2f8] px-1.5 py-0.5 text-[11px] font-bold text-[#162A4C]">{t(r.status === "DONE" ? "Fixed" : r.status === "IN_PROGRESS" ? "In progress" : "Received")}</span>
                {r.message}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

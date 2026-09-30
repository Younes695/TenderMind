import { useEffect, useState } from "react";
import { Mail, Copy } from "lucide-react";
import apiClient from "../api/client";
import { usePrefs } from "../i18n";

/** The decision summary for the owner / GM / tender manager. The text is editable; "Send by email"
 *  opens the user's own mail app with it — the platform never sends mail by itself. */
export default function DecisionSummaryMail({ tenderId }) {
  const { t, lang } = usePrefs();
  const [to, setTo] = useState({ name: "", email: "" });
  const [mail, setMail] = useState(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    const h = setTimeout(() => {
      apiClient.getDecisionSummary(tenderId, lang, to.name).then(setMail).catch((e) => setError(e.message));
    }, 300);
    return () => clearTimeout(h);
  }, [tenderId, lang, to.name]);
  const href = mail ? `mailto:${encodeURIComponent(to.email.trim())}?subject=${encodeURIComponent(mail.subject)}&body=${encodeURIComponent(mail.body)}` : "#";
  const input = "rounded-lg border border-[#d0d5dd] px-3 py-2 text-[14px]";
  return (
    <div data-testid="decision-summary" className="space-y-2">
      <div className="grid gap-2 sm:grid-cols-2">
        <input className={input} aria-label={t("Decision maker's name")} placeholder={t("Decision maker's name (e.g. General Manager)")}
          value={to.name} maxLength={120} onChange={(e) => setTo({ ...to, name: e.target.value })} />
        <input className={input} type="email" aria-label={t("Email")} placeholder={t("Email")} value={to.email}
          onChange={(e) => setTo({ ...to, email: e.target.value })} />
      </div>
      {error && <p className="text-[13px] text-[#b42318]">{error}</p>}
      {mail && (
        <>
          <p className="text-[13px] font-bold text-[#101828]">{mail.subject}</p>
          <textarea data-testid="decision-summary-body" dir="auto" className={`${input} h-72 w-full font-[inherit] leading-6`}
            value={mail.body} onChange={(e) => setMail({ ...mail, body: e.target.value })} />
          <div className="no-print flex flex-wrap gap-2">
            <a data-testid="send-summary" href={href} className="flex items-center gap-1.5 rounded-lg bg-[#162A4C] px-4 py-2 text-[14px] font-semibold text-white">
              <Mail size={15} /> {t("Send by email")}</a>
            <button type="button" onClick={() => { navigator.clipboard?.writeText(`${mail.subject}\n\n${mail.body}`); setCopied(true); }}
              className="flex items-center gap-1.5 rounded-lg border border-[#162A4C] px-4 py-2 text-[14px] font-semibold text-[#162A4C]">
              <Copy size={15} /> {copied ? t("Copied") : t("Copy")}</button>
            <span className="self-center text-[12px] text-[#667085]">{t("Opens your own email app — nothing is sent until you press Send there.")}</span>
          </div>
        </>
      )}
    </div>
  );
}

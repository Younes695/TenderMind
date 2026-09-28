import { useState } from "react";
import { Sparkles, Mail, Copy, X, ExternalLink } from "lucide-react";
import apiClient from "../api/client";
import { usePrefs } from "../i18n";

function usd(v) {
  if (v == null) return "—";
  return v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : `$${Math.round(v / 1e3)}K`;
}

const TONE = { BID: "border-[#bcd8c6] bg-[#e7f5ee] text-[#1f7a4d]", NO_BID: "border-[#f5c6c6] bg-[#fdf0f0] text-[#b42318]",
  REVIEW: "border-[#e6d3a3] bg-[#fdf4de] text-[#8a6a22]" };

/** Stage 5J — the rule-based decision explained in plain language, the share of
 *  mandatory requirements the company meets, an expected contract value from
 *  comparable awards, and a first-draft email to the tender owner. Loaded on
 *  demand so the workspace itself stays fast. */
export default function RecommendationPanel({ tenderId }) {
  const { lang, t } = usePrefs();
  const [rec, setRec] = useState(null);
  const [est, setEst] = useState(null);
  const [mail, setMail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const load = async () => {
    setBusy(true); setError(null);
    try {
      const [r, e] = await Promise.all([apiClient.getRecommendation(tenderId, lang), apiClient.getValueEstimate(tenderId)]);
      setRec(r); setEst(e);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  const draft = async () => {
    setBusy(true); setError(null);
    try { setMail(await apiClient.getEmailDraft(tenderId, lang)); } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  const btn = "flex items-center gap-1.5 rounded-lg bg-[#162A4C] px-4 py-2 text-[14px] font-semibold text-white disabled:opacity-50";

  return (
    <section data-testid="recommendation-panel" className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><Sparkles size={18} /> {t("AI recommendation")}</h2>
        <div className="flex gap-2">
          <button type="button" data-testid="load-recommendation" onClick={load} disabled={busy} className={btn}>{rec ? t("Refresh") : t("Show recommendation")}</button>
          <button type="button" data-testid="draft-email" onClick={draft} disabled={busy}
            className="flex items-center gap-1.5 rounded-lg border border-[#162A4C] px-4 py-2 text-[14px] font-semibold text-[#162A4C] disabled:opacity-50"><Mail size={15} /> {t("Draft email to the tender owner")}</button>
        </div>
      </div>
      {error && <p className="mt-3 text-[13px] text-[#b42318]">{error}</p>}
      {rec && (
        <div className="mt-4 space-y-3">
          <p data-testid="rec-headline" className={`rounded-xl border p-3 text-[15px] font-bold ${TONE[rec.decision] || "border-[#e4e7ec] bg-[#fafaf8] text-[#344054]"}`}>{rec.headline}</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl bg-[#faf9f6] p-4">
              <p className="text-[12px] font-bold text-[#667085]">{t("Company match to mandatory requirements")}</p>
              <p data-testid="match-percent" className="mt-1 text-[26px] font-black text-[#101828]">{rec.match_percent != null ? `${rec.match_percent}%` : "—"}</p>
              {rec.mandatory_total ? <p className="text-[12px] text-[#667085]">{t("{m} of {n} met with evidence", { m: rec.mandatory_met, n: rec.mandatory_total })}</p> : null}
            </div>
            <div className="rounded-xl bg-[#faf9f6] p-4">
              <p className="text-[12px] font-bold text-[#667085]">{t("Expected contract value")}</p>
              {est?.available ? (
                <>
                  <p data-testid="value-range" className="mt-1 text-[22px] font-black text-[#101828]">{usd(est.low)} – {usd(est.high)}</p>
                  <p className="text-[12px] text-[#667085]">{t("Median {m} from {n} similar awarded contracts ({kind}{kv})", { m: usd(est.median), n: est.comparables, kind: t(est.kind), kv: est.kv ? `, ~${est.kv} kV` : "" })}</p>
                  <p className="mt-1 text-[11px] text-[#98a2b3]">{t("Based on World Bank-financed contracts; scope and country conditions differ — use as a sanity check.")}</p>
                  {est.mixed_scope && <p className="text-[11px] text-[#8a6a22]">{t("Few contracts of the same scope — equipment-only and full EPC contracts are mixed, so the range is wider.")}</p>}
                  <details className="mt-2 text-[12px] text-[#475467]"><summary className="cursor-pointer">{t("Contracts used")}</summary>
                    <ul className="mt-1 space-y-1">{est.examples.map((x) => (
                      <li key={x.url}><a className="underline" href={x.url} target="_blank" rel="noopener noreferrer">{x.title}</a> · {x.country} · {usd(x.amount_usd)} <ExternalLink size={10} className="inline" /></li>))}
                    </ul>
                  </details>
                </>
              ) : <p className="mt-1 text-[13px] text-[#667085]">{t("Not enough comparable awarded contracts yet.")}</p>}
            </div>
          </div>
          {(rec.notes || []).map((n) => <p key={n} className="text-[13px] text-[#475467]">{n}</p>)}
          {(rec.sections || []).map((s) => (
            <div key={s.title}>
              <p className="text-[14px] font-bold text-[#101828]">{s.title}</p>
              <ul className="mt-1 list-disc space-y-0.5 ps-5 text-[13px] text-[#344054]">{s.items.map((i, k) => <li key={k}>{i}</li>)}</ul>
            </div>
          ))}
        </div>
      )}
      {mail && (
        <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="flex max-h-[88vh] w-full max-w-[760px] flex-col rounded-2xl bg-white p-5">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-[16px] font-bold text-[#101828]">{t("Email draft")}</p>
              <button type="button" aria-label={t("Close")} onClick={() => setMail(null)}><X size={18} /></button>
            </div>
            {!mail.company_profile_complete && <p className="mb-2 rounded-lg bg-[#fdf4de] p-2 text-[12px] text-[#8a6a22]">{t("Add your company details in Settings → Company profile to fill in the name and contact lines.")}</p>}
            <p className="text-[13px] text-[#344054]"><b>{t("Subject")}:</b> {mail.subject}</p>
            <textarea data-testid="email-body" defaultValue={mail.body} rows={16} className="mt-2 w-full flex-1 rounded-lg border border-[#d0d5dd] p-3 text-[13px]" />
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" className={btn} onClick={() => navigator.clipboard?.writeText(`${mail.subject}\n\n${mail.body}`)}><Copy size={14} /> {t("Copy")}</button>
              <a className="rounded-lg border border-[#d0d5dd] px-4 py-2 text-[14px] font-semibold text-[#162A4C]"
                href={`mailto:?subject=${encodeURIComponent(mail.subject)}&body=${encodeURIComponent(mail.body)}`}>{t("Open in email app")}</a>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

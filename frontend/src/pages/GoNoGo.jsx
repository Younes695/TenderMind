import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Info, FileText, AlertTriangle, Clock, Building2, Users } from "lucide-react";
import apiClient from "../api/client";
import { useT } from "../i18n";

function DecisionSupportCard({ tender, analysis, job }) {
  const t = useT();
  const reqs = analysis?.requirements || [];
  const mandatory = reqs.filter((r) => r.mandatory === true).length;
  const missingMandatory = reqs.filter((r) => r.mandatory == null).length;
  const unsupported = (analysis?.documents || []).filter((d) => d.extraction_status === "UNSUPPORTED" || d.document_status === "UNSUPPORTED").length;
  const deadlines = analysis?.deadlines?.length ?? 0;
  const hasCommercial = !!analysis?.commercial;
  const evidenceCount = analysis?.evidence?.length ?? 0;
  const status = analysis?.status || job?.status || "Not available";
  const isPartial = status === "PARTIAL";
  const isFailed = status === "FAILED";

  return (
    <div data-testid="decision-card" className="rounded-2xl border border-[#e5e1d9] bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-[15px] font-bold text-[#101828]">{tender.title || "Not available"}</p>
          <p className="text-[13px] text-[#667085]">{tender.id} • {tender.client || "Not available"} • {tender.location || "Not available"}</p>
        </div>
        <span className={`rounded-lg border px-2.5 py-1 text-[12px] font-bold ${status === "COMPLETED" ? "bg-[#e5f2eb] text-[#2E7D5B] border-[#bcd8c6]" : status === "PARTIAL" ? "bg-[#fdf4de] text-[#a98238] border-[#e6d3a3]" : status === "FAILED" ? "bg-[#fdf0f0] text-[#a33a3a] border-[#f5c6c6]" : "bg-[#f3f3f3] text-[#667085]"}`}>{status}</span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-[13px]">
        <div className="rounded-xl bg-[#faf9f6] p-3"><p className="font-bold text-[#667085] text-[11px]">Requirements</p><p className="mt-1 font-bold text-[#101828]">{reqs.length || t("Not available")}</p></div>
        <div className="rounded-xl bg-[#faf9f6] p-3"><p className="font-bold text-[#667085] text-[11px]">Mandatory</p><p className="mt-1 font-bold text-[#101828]">{mandatory || t("Not available")}</p></div>
        <div className="rounded-xl bg-[#faf9f6] p-3"><p className="font-bold text-[#667085] text-[11px]">Ambiguous (mandatory null)</p><p className="mt-1 font-bold text-[#101828]">{missingMandatory || t("Not identified")}</p></div>
        <div className="rounded-xl bg-[#faf9f6] p-3"><p className="font-bold text-[#667085] text-[11px]">Unsupported docs</p><p className="mt-1 font-bold text-[#101828]">{unsupported || t("Not identified")}</p></div>
        <div className="rounded-xl bg-[#faf9f6] p-3"><p className="font-bold text-[#667085] text-[11px]">Deadlines</p><p className="mt-1 font-bold text-[#101828]">{deadlines || t("Not identified")}</p></div>
        <div className="rounded-xl bg-[#faf9f6] p-3"><p className="font-bold text-[#667085] text-[11px]">Commercial</p><p className="mt-1 font-bold text-[#101828]">{hasCommercial ? t("Available") : t("Not available")}</p></div>
        <div className="rounded-xl bg-[#faf9f6] p-3"><p className="font-bold text-[#667085] text-[11px]">Evidence</p><p className="mt-1 font-bold text-[#101828]">{evidenceCount || t("Not identified")}</p></div>
        <div className="rounded-xl bg-[#faf9f6] p-3"><p className="font-bold text-[#667085] text-[11px]">Processing</p><p className="mt-1 font-bold text-[#101828]">{status}</p></div>
      </div>
      {isPartial && <p className="mt-3 rounded-xl bg-[#fdf4de] border border-[#e6d3a3] p-2 text-[12px] text-[#a98238]">Analysis incomplete (PARTIAL) - review required.</p>}
      {isFailed && <p className="mt-3 rounded-xl bg-[#fdf0f0] border border-[#f5c6c6] p-2 text-[12px] text-[#a33a3a]">Processing failed - review error.</p>}
      <div className="mt-3 flex gap-2">
        <Link to={`/tenders/${encodeURIComponent(tender.id)}`} className="rounded-xl bg-[#162A4C] px-4 py-2 text-[13px] font-bold text-white">{t("Open Workspace")}</Link>
        <span className="rounded-xl border border-[#e8e4dc] bg-[#faf9f6] px-3 py-2 text-[12px] text-[#667085]">{t("Decision requires management review.")}</span>
      </div>
    </div>
  );
}

function GoNoGo() {
  const t = useT();
  const [tenders, setTenders] = useState(null);
  const [analyses, setAnalyses] = useState({});
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    apiClient.listTenders()
      .then(async (data) => {
        const list = Array.isArray(data) ? data : [];
        if (cancelled) return;
        setTenders(list);
        // Fetch analysis for each tender (best effort, don't fail whole page if one fails)
        const map = {};
        await Promise.all(
          list.slice(0, 10).map(async (t) => {
            try {
              const a = await apiClient.getTenderAnalysis(t.id);
              // Only store if it looks like analysis (has requirements)
              if (a && a.requirements) map[t.id] = a;
              else if (a && a.status) map[t.id] = { status: a.status, ...a };
            } catch (e) {
              if (e.status === 404) map[t.id] = { status: "Not available" };
              else map[t.id] = { status: "Not available", error: e.message };
            }
          })
        );
        if (!cancelled) setAnalyses(map);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="min-h-screen bg-[#f8f7f3] p-4 sm:p-6 lg:p-8">
      <div className="mx-auto max-w-[1450px] space-y-6">
        <section className="rounded-2xl bg-[#101E38] p-6 sm:p-8">
          <p className="text-[13px] font-bold tracking-[0.18em] text-[#C8A96B]">DECISION SUPPORT</p>
          <h2 className="mt-2 text-[26px] font-black leading-tight text-white sm:text-[30px]">Decision requires management review.</h2>
          <p className="mt-2 max-w-[700px] text-[14px] leading-relaxed text-[#c5d0e6]">TenderMind organizes evidence and signals to support human decision-making. It does not produce an automatic BID/NO-BID recommendation. Review requirements, evidence, deadlines, commercial terms, and processing completeness before deciding.</p>
          <div className="mt-4 flex items-start gap-2 rounded-xl bg-white/10 p-3">
            <Info size={18} className="shrink-0 text-white" />
            <p className="text-[13px] leading-relaxed text-white">No fit score, risk score, or recommendation is generated in Stage 2B. Use this page to trace provenance and completeness.</p>
          </div>
          {error && <div data-testid="error-banner" className="mt-4 rounded-xl bg-[#fdf0f0] p-3 text-[14px] text-[#a33a3a]">{error}</div>}
        </section>

        <section className="rounded-2xl border border-[#e5e1d9] bg-white p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><Users size={18} /> {t("Tender Decision Support")}</h2>
          <p className="mt-1 text-[13px] text-[#667085]">{t('Each card shows backend-provided signals only. Missing fields are "Not available", not invented.')}</p>
          {tenders === null ? (
            <p className="mt-4 text-[14px] text-[#667085]">{t("Loading...")}</p>
          ) : tenders.length === 0 ? (
            <div data-testid="empty-state" className="mt-4 rounded-xl border border-[#e8e4dc] bg-[#faf9f6] p-6 text-center text-[15px] text-[#667085]">{t("No tenders yet — create a tender to see decision support.")}</div>
          ) : (
            <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
              {tenders.map((t) => (
                <DecisionSupportCard key={t.id} tender={t} analysis={analyses[t.id]} job={analyses[t.id]} />
              ))}
            </div>
          )}
          <div className="mt-6 flex flex-wrap gap-2">
            <Link to="/dashboard" className="rounded-xl bg-[#162A4C] px-5 py-2.5 text-[14px] font-bold text-white">{t("Dashboard")}</Link>
            <Link to="/tenders/new" className="rounded-xl border border-[#e2e6ee] px-5 py-2.5 text-[14px] font-bold text-[#162A4C]">{t("New Tender")}</Link>
          </div>
        </section>

        <section className="rounded-2xl border border-[#e5e1d9] bg-white p-5 sm:p-6">
          <h3 className="text-[14px] font-bold text-[#101828]">{t("Evidence-first guidance")}</h3>
          <p className="mt-2 text-[13px] leading-relaxed text-[#667085]">{t('For each requirement, open the tender workspace to see: summary → category → confidence → source document → page → source text → linked evidence. If evidence is unavailable, you will see "No evidence available" — no synthetic evidence is created.')}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {[t("Requirement → source document → page → source text → evidence"), t("Provenance visible, not hidden"), t("Human decision required")].map((s) => (
              <span key={s} className="rounded-full bg-[#faf9f6] border px-3 py-1 text-[12px] text-[#667085]">{s}</span>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

export default GoNoGo;

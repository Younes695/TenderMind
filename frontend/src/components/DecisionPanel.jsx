import { useCallback, useEffect, useRef, useState } from "react";
import { confirmRemoval } from "../utils/confirm";
import { CheckCircle2, AlertTriangle, XCircle, FileText, Upload, Trash2, Play, ChevronDown, ChevronRight, Scale } from "lucide-react";
import apiClient from "../api/client";
import { useT } from "../i18n";

const DECISION_STYLE = {
  BID: { bg: "bg-[#e7f6ec]", text: "text-[#1d7a3e]", border: "border-[#bfe5cc]", icon: CheckCircle2, label: "BID" },
  REVIEW: { bg: "bg-[#fdf5e6]", text: "text-[#9a6a12]", border: "border-[#f1dcae]", icon: AlertTriangle, label: "REVIEW" },
  NO_BID: { bg: "bg-[#fdf0f0]", text: "text-[#a33a3a]", border: "border-[#f5c6c6]", icon: XCircle, label: "NO BID" },
};

const STATUS_STYLE = {
  PASS: "bg-[#e7f6ec] text-[#1d7a3e]",
  FAIL: "bg-[#fdf0f0] text-[#a33a3a]",
  REVIEW: "bg-[#fdf5e6] text-[#9a6a12]",
  MISSING_EVIDENCE: "bg-[#eef1f6] text-[#475467]",
};

const RULE_TEXT = {
  HARD_GATE_FAIL: "A company document explicitly contradicts a mandatory gate.",
  MANDATORY_GATE_MISSING: "Mandatory qualification requirements have no company evidence yet.",
  MANDATORY_GATE_REVIEW: "Some mandatory evidence is ambiguous and needs human review.",
  EXPERIENCE_EVIDENCE_MISSING: "Mandatory requirements still lack company evidence.",
  COMMERCIAL_RISK_REVIEW: "High commercial risk needs review.",
  ALL_MANDATORY_PASS: "Every mandatory requirement is supported by company evidence.",
  HUMAN_OVERRIDE: "Decision set by a human reviewer.",
};

function StatusPill({ status }) {
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold ${STATUS_STYLE[status] || "bg-[#eef1f6] text-[#475467]"}`}>
      {status === "MISSING_EVIDENCE" ? "MISSING" : status || "—"}
    </span>
  );
}

function RequirementRow({ r }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  return (
    <div data-testid="decision-requirement" className="rounded-xl border border-[#eeeae3] bg-[#faf9f6]">
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-start gap-3 p-3 text-left">
        {open ? <ChevronDown size={16} className="mt-0.5 shrink-0" /> : <ChevronRight size={16} className="mt-0.5 shrink-0" />}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={r.status} />
            <span className="text-[11px] font-semibold text-[#667085]">{r.category}</span>
            {r.mandatory && <span className="text-[11px] font-semibold text-[#162A4C]">{t("Mandatory")}</span>}
          </div>
          <p className="mt-1 text-[14px] font-medium text-[#101828]">{r.requirement}</p>
        </div>
      </button>
      {open && (
        <div className="space-y-3 border-t border-[#eeeae3] p-3 pl-10 text-[13px]">
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wide text-[#667085]">{t("Tender source")}</div>
            <div className="mt-1 text-[#344054]">
              <FileText size={13} className="mr-1 inline" />
              {r.source_document || "—"} {r.page_or_section && `• ${r.page_or_section}`}
            </div>
            {r.source_quote && <blockquote className="mt-1 border-l-2 border-[#C8A96B] pl-2 italic text-[#475467]">"{r.source_quote}"</blockquote>}
          </div>
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wide text-[#667085]">{t("Company evidence")}</div>
            {r.evidence.length === 0 ? (
              <p className="mt-1 text-[#667085]">{r.reason || t('No company evidence found.')}</p>
            ) : (
              r.evidence.map((e) => (
                <div key={e.evidence_id} data-testid="decision-evidence" className="mt-1 rounded-lg border border-[#e5e1d9] bg-white p-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusPill status={e.status} />
                    <span className="text-[#344054]"><FileText size={13} className="mr-1 inline" />{e.source_document} • {e.page_or_section}</span>
                    {e.confidence && <span className="text-[11px] text-[#667085]">{t("confidence")} {e.confidence}</span>}
                  </div>
                  {e.quote && <blockquote className="mt-1 border-l-2 border-[#162A4C] pl-2 italic text-[#475467]">"{e.quote.slice(0, 400)}{e.quote.length > 400 ? "…" : ""}"</blockquote>}
                  {e.reason && <p className="mt-1 text-[12px] text-[#667085]">{e.reason}</p>}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function DecisionPanel({ tenderId, processingDone }) {
  const t = useT();
  const [detail, setDetail] = useState(null);
  const [docs, setDocs] = useState([]);
  const [evalJob, setEvalJob] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [override, setOverride] = useState({ reviewer: "", new_decision: "REVIEW", reason: "" });
  const fileRef = useRef(null);
  const pollRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const [d, c] = await Promise.all([apiClient.getDecisionDetail(tenderId), apiClient.listCompanyDocuments()]);
      setDetail(d);
      setDocs(c?.documents || []);
    } catch (e) {
      setError(e.message || "Failed to load decision");
    }
  }, [tenderId]);

  useEffect(() => {
    load();
    apiClient.getEvaluation(tenderId).then((j) => { if (j?.status === "RUNNING") { setEvalJob(j); poll(); } }).catch(() => {});
    return () => clearTimeout(pollRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenderId, processingDone]);

  function poll() {
    clearTimeout(pollRef.current);
    pollRef.current = setTimeout(async () => {
      try {
        const j = await apiClient.getEvaluation(tenderId);
        setEvalJob(j);
        if (j.status === "RUNNING") poll();
        else { if (j.status === "FAILED") setError(j.error || "Evaluation failed"); load(); }
      } catch (e) { setError(e.message); }
    }, 2000);
  }

  async function onUpload(e) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setBusy(true); setError("");
    try { await apiClient.uploadCompanyDocuments(files); await load(); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  async function onDelete(id, title) {
    if (!confirmRemoval(title, "document")) return;
    setBusy(true);
    try { await apiClient.deleteCompanyDocument(id); await load(); } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  async function onEvaluate() {
    setError("");
    try { const j = await apiClient.startEvaluation(tenderId); setEvalJob(j); poll(); }
    catch (err) { setError(err.message); }
  }

  async function onOverride(e) {
    e.preventDefault();
    if (!override.reviewer.trim() || !override.reason.trim()) { setError("Reviewer and reason are required for an override."); return; }
    setBusy(true); setError("");
    try { await apiClient.overrideDecision(tenderId, override); await load(); setOverride({ reviewer: "", new_decision: "REVIEW", reason: "" }); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  if (!detail) return null;
  if (!detail.available) {
    return (
      <section data-testid="decision-panel" className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
        <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><Scale size={18} /> {t("Bid decision")}</h2>
        <p className="mt-2 text-[14px] text-[#667085]">{detail.reason}</p>
      </section>
    );
  }

  const dec = detail.decision;
  const style = DECISION_STYLE[dec.decision] || DECISION_STYLE.REVIEW;
  const Icon = style.icon;
  const counts = detail.mandatory_status_counts || {};
  const reqs = detail.requirements || [];
  const visible = showAll ? reqs : reqs.filter((r) => r.mandatory);
  const running = evalJob?.status === "RUNNING";
  const isSeed = tenderId === "SA-2018-HV2";

  return (
    <section data-testid="decision-panel" className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><Scale size={18} /> {t("Bid decision")}</h2>
          <p className="mt-1 text-[13px] text-[#667085]">{t("Computed by deterministic rules from requirement evidence. Missing evidence is never treated as failure.")}</p>
        </div>
        <div data-testid="decision-badge" className={`flex items-center gap-3 rounded-xl border px-4 py-3 ${style.bg} ${style.border}`}>
          <Icon size={28} className={style.text} />
          <div>
            <div className={`text-[22px] font-black leading-none ${style.text}`}>{style.label}</div>
            <div className="mt-1 text-[12px] text-[#475467]">{t("Confidence")}: {dec.confidence}{dec.is_override ? ` • ${t("human override")}` : ""}</div>
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[["PASS", t("Supported")], ["FAIL", t("Contradicted")], ["REVIEW", t("Needs review")], ["MISSING_EVIDENCE", t("No evidence yet")]].map(([k, label]) => (
          <div key={k} className="rounded-xl border border-[#eeeae3] p-3">
            <div className="text-[22px] font-black text-[#101828]">{counts[k] || 0}</div>
            <div className="text-[12px] text-[#667085]">{label} {t("(mandatory)")}</div>
          </div>
        ))}
      </div>

      <div className="mt-4 space-y-1 text-[13px] text-[#344054]">
        {(dec.rules_triggered || []).map((r) => <p key={r}>• {RULE_TEXT[r] || r}</p>)}
      </div>

      {!isSeed && (
        <div className="mt-5 rounded-xl border border-dashed border-[#d0c7b5] bg-[#faf9f6] p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-[14px] font-bold text-[#101828]">{t("Company evidence")}</div>
              <div className="text-[12px] text-[#667085]">{t("Upload company profile, experience lists, certificates, financial statements (PDF, Word, Excel, TXT). Reused for every tender.")}</div>
            </div>
            <div className="flex gap-2">
              <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-[#d0d5dd] bg-white px-3 py-2 text-[13px] font-semibold text-[#162A4C]">
                <Upload size={15} /> {t("Upload")}
                <input ref={fileRef} data-testid="company-upload" type="file" multiple className="hidden" onChange={onUpload} disabled={busy} accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.md,.csv,.jpg,.jpeg,.png,.bmp,.gif,.tif,.tiff,.webp,.zip,.rar,.7z,.dxf,.bak" />
              </label>
              <button type="button" data-testid="evaluate-button" onClick={onEvaluate} disabled={running || docs.length === 0}
                className="flex items-center gap-2 rounded-lg bg-[#162A4C] px-3 py-2 text-[13px] font-semibold text-white disabled:opacity-50">
                <Play size={15} /> {running ? t("Evaluating {done}/{total}", { done: evalJob.done || 0, total: evalJob.total || "?" }) : t("Evaluate")}
              </button>
            </div>
          </div>
          {docs.length > 0 && (
            <ul className="mt-3 flex flex-wrap gap-2">
              {docs.map((d) => (
                <li key={d.id} className="flex items-center gap-2 rounded-lg border border-[#e5e1d9] bg-white px-2 py-1 text-[12px]">
                  <FileText size={13} /> {d.title}
                  <button type="button" aria-label={t("Remove {title}", { title: d.title })} onClick={() => onDelete(d.id, d.title)} disabled={busy}><Trash2 size={13} className="text-[#a33a3a]" /></button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {error && <div data-testid="decision-error" className="mt-3 rounded-lg bg-[#fdf0f0] p-3 text-[13px] text-[#a33a3a]">{error}</div>}

      <div className="mt-5 flex items-center justify-between">
        <h3 className="text-[14px] font-bold text-[#101828]">{t("Requirements and evidence ({n})", { n: visible.length })}</h3>
        <label className="flex items-center gap-2 text-[12px] text-[#475467]">
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> {t("Show informational (technical / schedule)")}
        </label>
      </div>
      <div className="mt-2 max-h-[560px] space-y-2 overflow-y-auto pr-1">
        {visible.map((r) => <RequirementRow key={r.requirement_id} r={r} />)}
      </div>

      <form onSubmit={onOverride} className="mt-5 grid gap-2 rounded-xl border border-[#eeeae3] p-4 sm:grid-cols-[1fr_140px_2fr_auto]">
        <input className="rounded-lg border border-[#d0d5dd] px-3 py-2 text-[13px]" placeholder={t("Reviewer name")} value={override.reviewer} onChange={(e) => setOverride({ ...override, reviewer: e.target.value })} />
        <select className="rounded-lg border border-[#d0d5dd] px-3 py-2 text-[13px]" value={override.new_decision} onChange={(e) => setOverride({ ...override, new_decision: e.target.value })}>
          <option value="BID">{t("BID")}</option><option value="REVIEW">{t("REVIEW")}</option><option value="NO_BID">{t("NO_BID")}</option>
        </select>
        <input className="rounded-lg border border-[#d0d5dd] px-3 py-2 text-[13px]" placeholder={t("Reason (kept in the audit trail)")} value={override.reason} onChange={(e) => setOverride({ ...override, reason: e.target.value })} />
        <button type="submit" disabled={busy} className="rounded-lg border border-[#162A4C] px-3 py-2 text-[13px] font-semibold text-[#162A4C]">{t("Override")}</button>
      </form>
    </section>
  );
}

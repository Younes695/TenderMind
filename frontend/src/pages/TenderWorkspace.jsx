import { useEffect, useState, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { CheckCircle2, Trash2, RefreshCw, Layers, FolderOpen, ListChecks, Users, FileText, AlertTriangle, Clock, Building2, Info, ChevronDown, ChevronUp, Search, Filter } from "lucide-react";
import apiClient from "../api/client";
import DecisionPanel from "../components/DecisionPanel";
import RecommendationPanel from "../components/RecommendationPanel";
import BidTools, { EligibilityBanner } from "../components/BidTools";
import { confirmRemoval } from "../utils/confirm";
import { useT } from "../i18n";

function StatusBadge({ status }) {
  const t = useT();
  const map = {
    COMPLETED: "bg-[#e5f2eb] text-[#2E7D5B] border-[#bcd8c6]",
    PARTIAL: "bg-[#fdf4de] text-[#a98238] border-[#e6d3a3]",
    FAILED: "bg-[#fdf0f0] text-[#a33a3a] border-[#f5c6c6]",
    PROCESSING: "bg-[#eef2f8] text-[#162A4C] border-[#c5d3e6]",
    QUEUED: "bg-[#eef2f8] text-[#162A4C] border-[#c5d3e6]",
    INELIGIBLE: "bg-[#fdf0f0] text-[#b42318] border-[#f5c6c6]",
  };
  const cls = map[status] || "bg-[#f3f3f3] text-[#667085] border-[#e8e4dc]";
  return <span className={`inline-flex rounded-lg border px-3 py-1 text-[12px] font-bold ${cls}`}>{status ? t(status) : t("Not available")}</span>;
}

function DocStatusBadge({ status }) {
  const t = useT();
  const map = {
    COMPLETE: "bg-[#e5f2eb] text-[#2E7D5B]",
    COMPLETED: "bg-[#e5f2eb] text-[#2E7D5B]",
    PARTIAL: "bg-[#fdf4de] text-[#a98238]",
    FAILED: "bg-[#fdf0f0] text-[#a33a3a]",
    UNSUPPORTED: "border border-[#f5c6c6] bg-[#fdf0f0] text-[#b42318]",
  };
  return <span className={`rounded-lg px-2.5 py-1 text-[12px] font-bold ${map[status] || "bg-[#f3f3f3] text-[#667085]"}`}>{status || t("Not available")}</span>;
}

function TenderWorkspace() {
  const t = useT();
  const { tender_id } = useParams();
  const id = tender_id;
  const [tender, setTender] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [analysisRaw, setAnalysisRaw] = useState(null);
  const [docs, setDocs] = useState(null);
  const [tenderDocs, setTenderDocs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedReq, setSelectedReq] = useState(null);
  const [filterCategory, setFilterCategory] = useState("ALL");
  const [filterMandatory, setFilterMandatory] = useState("ALL");
  const [filterEntity, setFilterEntity] = useState("ALL");
  const [search, setSearch] = useState("");
  const [removedTitles, setRemovedTitles] = useState([]);
  const [docBusy, setDocBusy] = useState(false);
  const [docNotice, setDocNotice] = useState(null);
  const [reloadTick, setReloadTick] = useState(0);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!id) {
      setError("No tender selected");
      setLoading(false);
      return;
    }
    let cancelled = false;
    async function load() {
      try {
        let t = null;
        try {
          t = await apiClient.getTender(id);
        } catch (e) {
          if (e.status === 404) {
            // A mistyped or deleted id used to render an empty "Not available" workspace.
            if (!cancelled) { setNotFound(true); setLoading(false); }
            return;
          }
        }
        const d = await apiClient.getTenderDocuments(id).catch(() => ({ documents: [] }));
        let a = null;
        let raw = null;
        try {
          const res = await apiClient.getTenderAnalysis(id);
          raw = res;
          // Distinguish analysis vs job status (backend returns status without requirements when not ready)
          if (res && res.requirements && Array.isArray(res.requirements)) {
            a = res;
          } else if (res && res.status) {
            // Job status, not analysis
            a = null;
            // Keep raw for processing status
          } else if (res && res.documents) {
            a = res;
          }
        } catch (e) {
          if (e.status === 404) {
            a = null;
            raw = null;
          } else if (e.data && e.data.status) {
            raw = e.data;
          } else {
            throw e;
          }
        }
        if (cancelled) return;
        setTender(t);
        setTenderDocs(d?.documents || []);
        // Prefer analysis documents if available, else tenderDocs
        setDocs(d?.documents || []);
        setAnalysis(a);
        setAnalysisRaw(raw);
        setLoading(false);
      } catch (e) {
        if (!cancelled) {
          setError(e.message || "Failed to load workspace");
          setLoading(false);
        }
      }
    }
    load();
    return () => { cancelled = true; };
  }, [id, reloadTick]);

  const requirements = analysis?.requirements || [];
  const evidenceList = analysis?.evidence || [];
  const deadlines = analysis?.deadlines || [];
  const commercial = analysis?.commercial;
  const risks = analysis?.risks || [];
  const derived = analysis?.derived_features || {};
  const processing = analysis?.processing || analysisRaw?.processing || null;
  const jobStatus = analysis?.status || analysisRaw?.status || processing?.status || null;
  const isPartial = jobStatus === "PARTIAL";
  const isFailed = jobStatus === "FAILED";
  const isProcessing = jobStatus === "QUEUED" || jobStatus === "PROCESSING";
  const hasAnalysis = !!analysis && Array.isArray(requirements);
  const canStartProcessing = (!jobStatus || isFailed) && (tenderDocs?.length || 0) > 0;
  // Stage 5H: open review items / questions come with the analysis response.
  const review = analysisRaw?.review || null;

  // Keep the status current while a job runs (the page used to load once).
  useEffect(() => {
    if (!isProcessing) return undefined;
    const timer = setInterval(() => setReloadTick((n) => n + 1), 10000);
    return () => clearInterval(timer);
  }, [isProcessing]);

  const filteredReqs = useMemo(() => {
    return requirements.filter((r) => {
      if (filterCategory !== "ALL" && r.category !== filterCategory) return false;
      if (filterMandatory !== "ALL") {
        const want = filterMandatory === "true";
        if ((r.mandatory ?? null) !== want && !(r.mandatory == null && filterMandatory === "null")) return false;
        if (filterMandatory === "null" && r.mandatory != null) return false;
      }
      if (filterEntity !== "ALL" && (r.applicable_entity || t("Not available")) !== filterEntity) return false;
      if (search && !`${r.summary || ""} ${r.category || ""} ${r.source_document || ""}`.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [requirements, filterCategory, filterMandatory, filterEntity, search]);

  const categories = useMemo(() => [...new Set(requirements.map((r) => r.category).filter(Boolean))], [requirements]);
  const entities = useMemo(() => [...new Set(requirements.map((r) => r.applicable_entity || t("Not available")))], [requirements]);
  const unsupportedDocs = useMemo(() => {
    const allDocs = analysis?.documents || docs || tenderDocs || [];
    return allDocs.filter((d) => (d.extraction_status === "UNSUPPORTED" || d.document_status === "UNSUPPORTED" || d.doc_type === "UNSUPPORTED" || d.document_type === "UNSUPPORTED"));
  }, [analysis, docs, tenderDocs]);

  // Uploaded files (DB rows) by stored title, so analysis rows can be removed.
  const docIdByTitle = new Map((tenderDocs || []).map((d) => [d.title, d.id]));
  const baseName = (name) => String(name || "").split("#")[0];

  const removeDocument = async (title) => {
    const docId = docIdByTitle.get(baseName(title));
    if (!docId) return;
    if (!confirmRemoval(baseName(title))) return;
    setDocBusy(true);
    setDocNotice(null);
    try {
      const res = await apiClient.deleteTenderDocument(id, docId);
      setRemovedTitles((prev) => [...prev, baseName(title)]);
      setTenderDocs((prev) => (prev || []).filter((d) => d.id !== docId));
      setDocNotice(res?.reprocess_needed ? "reprocess" : "removed");
    } catch (e) {
      setDocNotice(`error:${e.message || "Failed to remove file"}`);
    } finally {
      setDocBusy(false);
    }
  };

  const removeAllDocuments = async () => {
    if (!window.confirm("Remove all uploaded files from this tender?")) return;
    setDocBusy(true);
    setDocNotice(null);
    try {
      const res = await apiClient.deleteAllTenderDocuments(id);
      setRemovedTitles((prev) => [...prev, ...(res?.removed || []).map((d) => d.title)]);
      setTenderDocs([]);
      setDocNotice(res?.reprocess_needed ? "reprocess" : "removed");
    } catch (e) {
      setDocNotice(`error:${e.message || "Failed to remove files"}`);
    } finally {
      setDocBusy(false);
    }
  };

  const reprocess = async () => {
    setDocBusy(true);
    try {
      await apiClient.startTenderProcessing(id);
      window.location.reload();
    } catch (e) {
      setDocNotice(`error:${e.message || "Failed to start processing"}`);
      setDocBusy(false);
    }
  };

  if (!id) return <div className="p-8 text-center" data-testid="empty-state">{t("No tender selected")}</div>;
  if (loading) return <div className="p-8">{t("Loading workspace...")}</div>;
  if (notFound) return (
    <div data-testid="tender-not-found" className="m-8 rounded-xl border border-[#e8e4dc] bg-white p-6">
      <p className="text-[16px] font-bold text-[#101828]">{t("Tender not found")}</p>
      <p className="mt-1 text-[14px] text-[#667085]">{t("No tender with ID {id} exists for your account. Check the link, or open it from the list.", { id })}</p>
      <Link to="/tenders" className="mt-4 inline-block rounded-lg bg-[#162A4C] px-4 py-2 text-[14px] font-semibold text-white">{t("Back to tenders")}</Link>
    </div>
  );
  if (error) return <div data-testid="error-banner" className="m-8 rounded-xl border border-[#f5c6c6] bg-[#fdf0f0] p-4 text-[#a33a3a]">{error}</div>;

  const title = tender?.title || analysis?.tender?.title || analysis?.title || t("Not available");
  const client = tender?.client || analysis?.client || t("Not available");
  const location = tender?.location || analysis?.location || t("Not available");

  // Helper to get evidence for a requirement
  const getEvidenceForReq = (reqId) => evidenceList.filter((e) => e.requirement_id === reqId);

  return (
    <div className="min-h-screen bg-[#f8f7f3] p-4 sm:p-6 lg:p-8">
      <div className="mx-auto max-w-[1450px] space-y-6">
        {/* Tender Overview */}
        <section data-testid="tender-overview" className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-[26px] font-black leading-tight text-[#101828] sm:text-[30px]">
                {id} <span className="font-medium text-[#667085] text-[20px]">· {title}</span>
              </h1>
              <div className="mt-2 flex flex-wrap gap-2 text-[14px] text-[#667085]">
                <span className="flex items-center gap-1"><Building2 size={14} /> {client}</span>
                <span>•</span>
                <span>{location}</span>
                <span>•</span>
                <span>{t("{n} documents", { n: tenderDocs?.length ?? docs?.length ?? 0 })}</span>
              </div>
            </div>
            <StatusBadge status={jobStatus} />
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl bg-[#faf9f6] p-3">
              <p className="text-[12px] font-bold tracking-wide text-[#667085]">{t("Tender ID")}</p>
              <p className="mt-1 text-[14px] font-bold text-[#101828] break-all">{id}</p>
            </div>
            <div className="rounded-xl bg-[#faf9f6] p-3">
              <p className="text-[12px] font-bold tracking-wide text-[#667085]">{t("Title")}</p>
              <p className="mt-1 text-[14px] font-bold text-[#101828]">{title}</p>
            </div>
            <div className="rounded-xl bg-[#faf9f6] p-3">
              <p className="text-[12px] font-bold tracking-wide text-[#667085]">{t("Client")}</p>
              <p className="mt-1 text-[14px] font-bold text-[#101828]">{client}</p>
            </div>
            <div className="rounded-xl bg-[#faf9f6] p-3">
              <p className="text-[12px] font-bold tracking-wide text-[#667085]">{t("Location")}</p>
              <p className="mt-1 text-[14px] font-bold text-[#101828]">{location}</p>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2 text-[13px]">
            <span className="rounded-lg bg-[#eef2f8] px-2.5 py-1">{t("Documents")}: {tenderDocs?.length ?? t("Not available")}</span>
            <span className="rounded-lg bg-[#eef2f8] px-2.5 py-1">{t("Requirements")}: {requirements.length || t("Not available")}</span>
            <span className="rounded-lg bg-[#eef2f8] px-2.5 py-1">{t("Processing")}: {jobStatus ? t(jobStatus) : t("Not available")}</span>
            <span className="rounded-lg bg-[#eef2f8] px-2.5 py-1">{t("Analysis")}: {hasAnalysis ? t("Available") : t("Not available")}</span>
          </div>
        </section>

        {/* Processing Status */}
        <section data-testid="processing-status" className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><Clock size={18} /> {t("Processing Status")}</h2>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <StatusBadge status={jobStatus} />
            {processing?.progress != null ? (
              <span className="text-[14px] text-[#667085]">{processing.progress}%</span>
            ) : analysisRaw?.progress != null ? (
              <span className="text-[14px] text-[#667085]">{analysisRaw.progress}%</span>
            ) : (
              <span className="text-[14px] text-[#667085]">{t("Progress not available")}</span>
            )}
            {processing?.job_id && <span className="text-[12px] text-[#667085]">{t("Job")} {processing.job_id}</span>}
            {analysisRaw?.job_id && !processing?.job_id && <span className="text-[12px] text-[#667085]">{t("Job")} {analysisRaw.job_id}</span>}
          </div>
          {isPartial && <div className="mt-3 rounded-xl bg-[#fdf4de] border border-[#e6d3a3] p-3 text-[14px] text-[#a98238]">{t("Analysis is incomplete (PARTIAL) — some documents failed or were unsupported. Review documents and risks below.")}</div>}
          {isFailed && <div className="mt-3 rounded-xl bg-[#fdf0f0] border border-[#f5c6c6] p-3 text-[14px] text-[#a33a3a]">{t("Processing failed")}{analysisRaw?.last_error ? `: ${analysisRaw.last_error}` : processing?.last_error ? `: ${processing.last_error}` : ""}</div>}
          {isProcessing && <div className="mt-3 rounded-xl bg-[#eef2f8] border border-[#c5d3e6] p-3 text-[14px] text-[#162A4C]">{t("Processing — current stage: {stage}", { stage: processing?.current_stage || analysisRaw?.current_stage || t("Not available") })}</div>}
          {!jobStatus && <div data-testid="empty-state" className="mt-3 text-[14px] text-[#667085]">{t("No processing information")}</div>}
          {canStartProcessing && (
            <button type="button" data-testid="start-processing" onClick={reprocess} disabled={docBusy}
              className="mt-3 flex items-center gap-1.5 rounded-lg bg-[#162A4C] px-4 py-2 text-[14px] font-semibold text-white disabled:opacity-50">
              <RefreshCw size={14} /> {isFailed ? t("Retry processing") : t("Start processing")}
            </button>
          )}
          <div className="mt-3 text-[12px] text-[#667085]">
            {processing?.documents_total != null && <span>{t("Documents total")}: {processing.documents_total} • </span>}
            {processing?.documents_processed != null && <span>{t("Processed")}: {processing.documents_processed} • </span>}
            {processing?.documents_failed != null && <span>{t("Failed")}: {processing.documents_failed} • </span>}
            {processing?.documents_unsupported != null && <span>{t("Unsupported")}: {processing.documents_unsupported}</span>}
          </div>
          {(processing?.analysis_coverage || processing?.document_status_counts) && (
            <div className="mt-2 text-[12px] text-[#667085]" data-testid="coverage-line">
              <span>{t("Processing")}: {jobStatus ? t(jobStatus) : t("Not available")} • {t("Analysis coverage")}: {processing.analysis_coverage || t("Not available")}</span>
              {processing?.document_status_counts && <span> • {t("Complete")}: {processing.document_status_counts.complete ?? "—"} • {t("Failed")}: {processing.document_status_counts.failed ?? "—"} • {t("Unsupported")}: {processing.document_status_counts.unsupported ?? "—"}</span>}
            </div>
          )}
        </section>

        {review && (review.missing_open > 0 || review.question_open > 0) && (
          <section data-testid="review-summary" className="flex flex-col gap-3 rounded-2xl border border-[#e6d3a3] bg-[#fdf8ec] p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-2 text-[14px] text-[#8a6a22]">
              <AlertTriangle size={18} className="mt-0.5 shrink-0" />
              <span>
                <b>{t("Needs review")}:</b> {t("{missing} missing or unreadable item(s) and {question} unclear point(s) in this tender.", { missing: review.missing_open, question: review.question_open })}
              </span>
            </div>
            <div className="flex shrink-0 gap-2">
              {review.missing_open > 0 && <Link to="/notifications" className="rounded-lg bg-[#162A4C] px-3 py-1.5 text-[13px] font-semibold text-white">{t("Review missing")}</Link>}
              {review.question_open > 0 && <Link to={`/qa?tender=${encodeURIComponent(id)}`} className="rounded-lg border border-[#162A4C] px-3 py-1.5 text-[13px] font-semibold text-[#162A4C]">{t("Open Q&A")}</Link>}
            </div>
          </section>
        )}

        {jobStatus === "INELIGIBLE" && <EligibilityBanner tenderId={id} onContinue={() => window.location.reload()} />}
        {jobStatus && jobStatus !== "PROCESSING" && jobStatus !== "QUEUED" && <RecommendationPanel tenderId={id} />}
        {tender && <BidTools tenderId={id} outcome={tender.outcome} />}

        {/* Bid decision with evidence (Stage 5C) */}
        {jobStatus !== "PROCESSING" && jobStatus !== "QUEUED" && (
          <DecisionPanel tenderId={id} processingDone={jobStatus} />
        )}

        {/* Documents */}
        <section data-testid="documents-section" className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
          <div className="flex items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><FolderOpen size={18} /> {t("Documents")}</h2>
            {(tenderDocs || []).length > 0 && !isProcessing && (
              <button type="button" data-testid="remove-all-docs" onClick={removeAllDocuments} disabled={docBusy} className="text-[13px] font-semibold text-[#a33a3a] hover:underline disabled:opacity-50">{t("Remove all")}</button>
            )}
          </div>
          {docNotice === "reprocess" && (
            <div data-testid="reprocess-notice" className="mt-3 flex flex-col gap-2 rounded-xl border border-[#e6d3a3] bg-[#fdf4de] p-3 text-[13px] text-[#8a6a22] sm:flex-row sm:items-center sm:justify-between">
              <span>{t("File removed. The results below were computed with it — reprocess to update them.")}</span>
              {(tenderDocs || []).length > 0 && (
                <button type="button" onClick={reprocess} disabled={docBusy} className="flex shrink-0 items-center gap-1.5 rounded-lg bg-[#162A4C] px-3 py-1.5 font-semibold text-white disabled:opacity-50"><RefreshCw size={14} /> {t("Reprocess")}</button>
              )}
            </div>
          )}
          {docNotice === "removed" && <div className="mt-3 rounded-xl bg-[#e5f2eb] p-3 text-[13px] text-[#2E7D5B]">{t("File removed — it will not be processed.")}</div>}
          {docNotice?.startsWith("error:") && <div className="mt-3 rounded-xl bg-[#fdf0f0] p-3 text-[13px] text-[#a33a3a]">{docNotice.slice(6)}</div>}
          {(() => {
            const sourceDocs = analysis?.documents?.length ? analysis.documents : (tenderDocs?.length ? tenderDocs : docs || []);
            const allDocs = (sourceDocs || []).filter((d) => !removedTitles.includes(baseName(d.filename || d.title || d.original_filename)));
            if (!allDocs || allDocs.length === 0) return <div data-testid="empty-state" className="mt-3 rounded-xl bg-[#faf9f6] p-4 text-center text-[14px] text-[#667085]">{t("No documents")}</div>;
            return (
              <div className="mt-4 space-y-3">
                {allDocs.map((d, idx) => {
                  const filename = d.filename || d.title || d.original_filename || t("Not available");
                  const docType = d.document_type || d.doc_type || t("Not available");
                  const status = d.extraction_status || d.document_status || (d.doc_type === "UNSUPPORTED" ? "UNSUPPORTED" : t("Not available"));
                  const pageCount = d.page_count ?? t("Not available");
                  const size = d.text_length ?? d.file_size ?? d.size ?? t("Not available");
                  const error = d.error || d.processing_error || null;
                  return (
                    <div key={`${filename}-${idx}`} data-testid="document-item" className="flex flex-col gap-2 rounded-xl border border-[#eeeae3] p-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex items-center gap-3 min-w-0">
                        <FileText size={20} className="shrink-0 text-[#162A4C]" />
                        <div className="min-w-0">
                          <p className="truncate text-[14px] font-bold text-[#101828]">{filename}</p>
                          <p className="text-[12px] text-[#667085]">{t("Type")}: {docType} • {t("Pages")}: {pageCount} • {t("Size")}: {size} {typeof size === "number" ? "bytes/chars" : ""}</p>
                          {error && <p className="text-[12px] text-[#a33a3a]">{t("Error")}: {error}</p>}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <DocStatusBadge status={status} />
                        {docIdByTitle.has(baseName(filename)) && !isProcessing && (
                          <button type="button" aria-label={t("Remove {filename}", { filename })} onClick={() => removeDocument(filename)} disabled={docBusy} className="flex h-8 w-8 items-center justify-center rounded-lg text-[#667085] hover:bg-[#fdf0f0] hover:text-[#a33a3a] disabled:opacity-50">
                            <Trash2 size={16} />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
                {unsupportedDocs.length > 0 && <div className="rounded-xl border border-[#f5c6c6] bg-[#fdf0f0] p-3 text-[13px] text-[#b42318]">{t("{n} unsupported document(s) — processing marked as UNSUPPORTED, no extraction performed.", { n: unsupportedDocs.length })}</div>}
              </div>
            );
          })()}
        </section>

        {/* Requirements */}
        <section data-testid="requirements-section" className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><ListChecks size={18} /> {t("Requirements")} — {requirements.length || 0}</h2>
            {hasAnalysis && <span className="text-[13px] text-[#667085]">{t("{n} shown", { n: filteredReqs.length })}</span>}
          </div>
          {!hasAnalysis ? (
            <div data-testid="empty-state" className="mt-3 rounded-xl bg-[#faf9f6] p-4 text-center text-[14px] text-[#667085]">{t("No requirements — analysis not available or empty")}</div>
          ) : (
            <>
              {/* Filters */}
              <div className="mt-4 flex flex-wrap gap-2">
                <div className="flex items-center gap-1">
                  <Filter size={14} className="text-[#667085]" />
                  <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)} className="rounded-lg border border-[#e8e4dc] bg-white px-2 py-1 text-[13px]">
                    <option value="ALL">{t("All categories")}</option>
                    {categories.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <select value={filterMandatory} onChange={(e) => setFilterMandatory(e.target.value)} className="rounded-lg border border-[#e8e4dc] bg-white px-2 py-1 text-[13px]">
                  <option value="ALL">{t("All mandatory")}</option>
                  <option value="true">{t("Mandatory: true")}</option>
                  <option value="false">{t("Mandatory: false")}</option>
                  <option value="null">{t("Mandatory: Not available")}</option>
                </select>
                <select value={filterEntity} onChange={(e) => setFilterEntity(e.target.value)} className="rounded-lg border border-[#e8e4dc] bg-white px-2 py-1 text-[13px]">
                  <option value="ALL">{t("All entities")}</option>
                  {entities.map((en) => <option key={en} value={en}>{en}</option>)}
                </select>
                <div className="flex items-center gap-1">
                  <Search size={14} className="text-[#667085]" />
                  <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t("Search summary")} className="rounded-lg border border-[#e8e4dc] px-2 py-1 text-[13px]" />
                </div>
              </div>

              {filteredReqs.length === 0 ? (
                <div data-testid="empty-state" className="mt-4 p-4 text-center text-[14px] text-[#667085]">{t("No requirements match filters")}</div>
              ) : (
                <div className="mt-4 space-y-3">
                  {filteredReqs.map((r) => {
                    const isOpen = selectedReq === r.requirement_id;
                    const evs = getEvidenceForReq(r.requirement_id);
                    return (
                      <div key={r.requirement_id} data-testid="requirement-item" className="rounded-xl border border-[#eeeae3] bg-[#faf9f6] p-4">
                        <div className="flex items-start justify-between gap-3 cursor-pointer" onClick={() => setSelectedReq(isOpen ? null : r.requirement_id)}>
                          <div className="min-w-0 flex-1">
                            <p className="text-[14px] font-bold text-[#101828]">{r.summary || t("Not available")}</p>
                            <p className="mt-1 flex flex-wrap gap-2 text-[12px] text-[#667085]">
                              <span className="rounded bg-white border px-2 py-0.5">{r.category || t("Not available")}</span>
                              <span className="rounded bg-white border px-2 py-0.5">{t("Mandatory")}: {r.mandatory == null ? t("Not available") : String(r.mandatory)}</span>
                              <span className="rounded bg-white border px-2 py-0.5">{t("Entity")}: {r.applicable_entity || t("Not available")}</span>
                              <span className="rounded bg-white border px-2 py-0.5">{t("Confidence")}: {r.confidence ?? t("Not available")}</span>
                            </p>
                            <p className="mt-1 text-[12px] text-[#667085]">{t("Source")}: {r.source_document || t("Not available")} • {t("Page")} {r.page_number ?? t("Not available")}</p>
                            {r.provenance?.quote_en && <p className="mt-1 text-[12px] italic text-[#667085]">"{r.provenance.quote_en}"</p>}
                            {!r.provenance?.quote_en && r.source_text && <p className="mt-1 text-[12px] italic text-[#667085]">"{String(r.source_text).slice(0, 200)}"</p>}
                          </div>
                          <button className="shrink-0 text-[#162A4C]">{isOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}</button>
                        </div>
                        {isOpen && (
                          <div data-testid="requirement-detail" className="mt-3 border-t border-[#eeeae3] pt-3">
                            <p className="text-[13px] font-bold text-[#101828]">{t("Evidence")}</p>
                            {evs.length === 0 ? (
                              <p className="mt-1 text-[13px] text-[#667085]">{t("No evidence available")}</p>
                            ) : (
                              <div className="mt-2 space-y-2">
                                {evs.map((e) => (
                                  <div key={e.evidence_id} data-testid="evidence-item" className="rounded-lg bg-white border p-3">
                                    <p className="text-[13px] font-bold text-[#101828]">{e.fact || e.summary || t("Not available")}</p>
                                    <p className="text-[12px] text-[#667085]">{t("Source")}: {e.source_document || t("Not available")} • {t("Page")} {e.page_number ?? t("Not available")} • {t("Confidence")}: {e.confidence ?? t("Not available")}</p>
                                    {e.provenance?.quote_en && <p className="text-[12px] italic text-[#667085]">"{e.provenance.quote_en}"</p>}
                                  </div>
                                ))}
                              </div>
                            )}
                            <div className="mt-2 text-[12px] text-[#667085]">
                              <p>{t("Requirement ID")}: {r.requirement_id || t("Not available")}</p>
                              <p>{t("Extraction method")}: {r.extraction_method || t("Not available")}</p>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </section>

        {/* Deadlines */}
        <section data-testid="deadlines-section" className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><Clock size={18} /> {t("Deadlines / Schedule")}</h2>
          {!deadlines || deadlines.length === 0 ? (
            <div data-testid="empty-state" className="mt-3 rounded-xl bg-[#faf9f6] p-4 text-center text-[14px] text-[#667085]">{t("No deadlines identified")}</div>
          ) : (
            <div className="mt-4 space-y-3">
              {deadlines.map((d, idx) => (
                <div key={idx} data-testid="deadline-item" className="rounded-xl border border-[#eeeae3] p-4">
                  <p className="text-[14px] font-bold text-[#101828]">{t("Type")}: {d.type || t("Not available")} • {t("Date")}: {d.date || t("Not available")}</p>
                  {d.source_snippet && <p className="mt-1 text-[12px] italic text-[#667085]">"{d.source_snippet}"</p>}
                  {d.source_document && <p className="text-[12px] text-[#667085]">{t("Source")}: {d.source_document} {d.page_number ? `${t("Page")} ${d.page_number}` : ""}</p>}
                  {d.raw_text && <p className="text-[12px] text-[#667085]">{t("Raw")}: {d.raw_text}</p>}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Commercial */}
        <section data-testid="commercial-section" className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><Building2 size={18} /> {t("Commercial")}</h2>
          {!commercial ? (
            <div data-testid="empty-state" className="mt-3 rounded-xl bg-[#faf9f6] p-4 text-center text-[14px] text-[#667085]">{t("Commercial information not available")}</div>
          ) : (
            <div className="mt-4 space-y-2 text-[14px] text-[#101828]">
              {Object.entries(commercial).map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3 border-b border-[#eeeae3] py-2 last:border-0">
                  <span className="font-bold text-[#667085]">{k}</span>
                  <span>{v == null || v === "" ? t("Not available") : String(v)}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Risks / Missing / Ambiguities / Unsupported */}
        <section data-testid="risks-section" className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><AlertTriangle size={18} /> {t("Risks / Missing / Ambiguities")}</h2>
          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <h3 className="text-[14px] font-bold text-[#101828]">{t("Risks")}</h3>
              {!risks || risks.length === 0 ? (
                <p className="mt-2 text-[13px] text-[#667085]">{t("Not identified")}</p>
              ) : (
                <div className="mt-2 space-y-2">
                  {risks.map((r, idx) => (
                    <div key={r.risk_id || idx} data-testid="risk-item" className="rounded-xl border border-[#eeeae3] p-3">
                      <p className="text-[13px] font-bold text-[#101828]">{r.description || t("Not available")}</p>
                      <p className="text-[12px] text-[#667085]">{t("Severity")}: {r.severity ?? t("Not available")} • {t("Type")}: {r.type || t("Not available")}</p>
                      {r.mitigation && <p className="text-[12px] text-[#667085]">{t("Mitigation")}: {r.mitigation}</p>}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div>
              <h3 className="text-[14px] font-bold text-[#101828]">{t("Missing / Ambiguous")}</h3>
              <div className="mt-2 space-y-2 text-[13px] text-[#667085]">
                {requirements.filter((r) => r.mandatory == null).length > 0 && (
                  <p>{t("{n} requirement(s) with mandatory = Not available (Ambiguous)", { n: requirements.filter((r) => r.mandatory == null).length })}</p>
                )}
                {derived.mandatory_missing_count != null && <p>{t("Mandatory missing count")}: {derived.mandatory_missing_count}</p>}
                {requirements.filter((r) => !r.source_document).length > 0 && <p>{t("{n} requirement(s) without provenance — Missing", { n: requirements.filter((r) => !r.source_document).length })}</p>}
                {unsupportedDocs.length > 0 && <p>{t("{n} unsupported document(s) — Unsupported", { n: unsupportedDocs.length })}</p>}
                {requirements.filter((r) => r.mandatory == null).length === 0 && derived.mandatory_missing_count == null && requirements.filter((r) => !r.source_document).length === 0 && unsupportedDocs.length === 0 && <p>{t("Not identified")}</p>}
              </div>
            </div>
          </div>
          {unsupportedDocs.length > 0 && (
            <div className="mt-4">
              <h4 className="text-[13px] font-bold text-[#101828]">{t("Unsupported documents")}</h4>
              <div className="mt-2 space-y-2">
                {unsupportedDocs.map((d, idx) => (
                  <div key={idx} data-testid="unsupported-doc" className="rounded-xl border border-[#f5c6c6] bg-[#fdf0f0] p-3 text-[12px] text-[#a33a3a]">
                    {d.filename || d.title || t("Not available")} — {d.extraction_status || d.document_status || "UNSUPPORTED"} {d.error ? `• ${d.error}` : ""}
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* Pipeline intelligence (Stage 4F additive sections; rendered only when present) */}
        {(derived.commercial_facts || derived.schedule_facts || derived.gaps || derived.ambiguities || derived.conflicts || derived.risk_signals || derived.synthesis) && (
        <section className="rounded-2xl bg-white p-5 shadow-sm sm:p-6" data-testid="intelligence-section">
          <h3 className="text-[14px] font-bold text-[#101828]">{t("Pipeline intelligence")}</h3>
          <div className="mt-2 space-y-2 text-[13px] text-[#667085]">
            {derived.commercial_facts && <p data-testid="intel-commercial">{t("Currency")}: {derived.commercial_facts.currency || t("Not available")} • {t("Payment")}: {derived.commercial_facts.payment_terms || t("Not available")} • {t("Line items")}: {(derived.commercial_facts.line_items || []).length}</p>}
            {derived.schedule_facts && <p data-testid="intel-schedule">{t("Schedule facts")}: {derived.schedule_facts.length}</p>}
            {derived.gaps && <p data-testid="intel-gaps">{t("Package gaps")}: {derived.gaps.length}</p>}
            {derived.ambiguities && <p data-testid="intel-ambiguities">{t("Ambiguity groups")}: {derived.ambiguities.length}{derived.ambiguity_report ? ` (${derived.ambiguity_report.raw_signals ?? "?"} ${t("signals")}, −${derived.ambiguity_report.reduction_pct ?? "?"}%)` : ""} — {t("requires clarification/review")}</p>}
            {derived.ambiguities && derived.ambiguities.length > 0 && (
              <div className="space-y-1" data-testid="intel-ambiguity-groups">
                {derived.ambiguities.slice(0, 20).map((g, i) => (
                  <details key={g.group_id || i} className="rounded-lg border border-[#eeeae3] p-2">
                    <summary className="cursor-pointer text-[12px] font-bold text-[#101828]">{g.ambiguity_type || t("ambiguity")} • {g.signal_count ?? 1} {t("signal(s)")} • {g.source_document || t("unknown source")}</summary>
                    <p className="mt-1 text-[12px] text-[#667085]">{g.description || t("Not available")}</p>
                    {(g.evidence || []).length > 0 && <p className="mt-1 text-[11px] text-[#667085]">{t("Evidence")}: {g.evidence.slice(0, 3).join("; ")}</p>}
                  </details>
                ))}
              </div>
            )}
            {derived.conflicts && <p data-testid="intel-conflicts">{t("Conflicts")}: {derived.conflicts.length}</p>}
            {derived.risk_signals && <p data-testid="intel-risks">{t("Risk signals")}: {derived.risk_signals.length} {t("(observations only, no severity)")}</p>}
            {derived.synthesis && <p data-testid="intel-synthesis">{t("Synthesis")}: {derived.synthesis.status || t("Not available")}</p>}
          </div>
        </section>
        )}

        {/* Evidence provenance note */}
        <section className="rounded-2xl bg-[#162A4C] p-5 sm:p-6">
          <p className="flex items-center gap-2 text-[13px] font-bold tracking-wide text-[#C8A96B]"><Info size={16} /> {t("Evidence-first")}</p>
          <p className="mt-2 text-[14px] leading-relaxed text-[#c5d0e6]">{t("Every requirement traces to source document → page → source text → evidence. No synthetic evidence is generated. Use this workspace to prepare for management review — final decision remains human.")}</p>
        </section>

        <div className="flex flex-col gap-3 sm:flex-row">
          <Link to="/dashboard" className="flex h-[54px] items-center justify-center rounded-xl bg-[#162A4C] px-8 text-[16px] font-bold text-white">{t("Back to Dashboard")}</Link>
          <Link to="/tenders/new" className="flex h-[54px] items-center justify-center rounded-xl border border-[#e2e6ee] bg-white px-8 text-[16px] font-bold text-[#101828]">{t("New Tender")}</Link>
          <Link to="/go-no-go" className="flex h-[54px] items-center justify-center rounded-xl border border-[#e2e6ee] bg-white px-8 text-[16px] font-bold text-[#101828]">{t("Decision Support")}</Link>
        </div>
      </div>
    </div>
  );
}

export default TenderWorkspace;

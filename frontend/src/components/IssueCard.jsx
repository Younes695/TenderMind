import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, RotateCcw, FileText } from "lucide-react";
import apiClient from "../api/client";
import { useT } from "../i18n";

const PRIORITY_STYLE = {
  HIGH: "bg-[#fdf0f0] text-[#b42318]",
  MEDIUM: "bg-[#fdf4de] text-[#8a6a22]",
  LOW: "bg-[#eef2f8] text-[#344054]",
};

/** One review item or question. `withAnswer` shows the answer box (Q&A). */
export default function IssueCard({ issue, withAnswer = false, showTender = false, onChange }) {
  const t = useT();
  const [answer, setAnswer] = useState(issue.answer || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const resolved = issue.status === "RESOLVED";

  // Translate issue titles from server, with special handling for page-count titles
  const translatedTitle = (() => {
    const match = issue.title?.match(/^(\d+) scanned page\(s\) could not be read reliably$/);
    if (match) return t("{n} scanned page(s) could not be read reliably", { n: parseInt(match[1]) });
    const unk = issue.title?.match(/^(\d+) requirements could not be classified$/);
    if (unk) return t("{n} requirements could not be classified", { n: parseInt(unk[1]) });
    const dis = issue.title?.match(/^Documents disagree: (.+)$/);
    if (dis) return t("Documents disagree: {what}", { what: t(dis[1]) });
    return t(issue.title);
  })();

  const save = async (patch) => {
    setBusy(true);
    setError(null);
    try {
      const updated = await apiClient.updateIssue(issue.id, patch);
      onChange?.(updated);
    } catch (e) {
      setError(e.message || "Could not save");
    } finally {
      setBusy(false);
    }
  };

  return (
    <article data-testid="issue-card" className={`rounded-xl border p-4 ${resolved ? "border-[#e4e7ec] bg-[#fafaf8] opacity-80" : "border-[#e8e4dc] bg-white"}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[15px] font-bold text-[#101828]">{translatedTitle}</p>
          {showTender && (
            <Link to={`/tenders/${encodeURIComponent(issue.tender_id)}`} className="text-[12px] font-semibold text-[#162A4C] underline">
              {issue.tender_id}
            </Link>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className={`rounded-md px-2 py-0.5 text-[11px] font-bold ${PRIORITY_STYLE[issue.priority] || PRIORITY_STYLE.LOW}`}>{t(issue.priority)}</span>
          <span className={`rounded-md px-2 py-0.5 text-[11px] font-bold ${resolved ? "bg-[#e7f5ee] text-[#1f7a4d]" : "bg-[#f2f4f7] text-[#344054]"}`}>{resolved ? t("Resolved") : t("Open|status")}</span>
        </div>
      </div>
      {issue.kind === "referenced-form-absent" && (
        <p className="mt-2 text-[13px] text-[#475467]">{t("These forms / annexes / appendices are mentioned in the files below, but no uploaded file carries their name. Many are sections inside the same file or standards — upload only the ones that are really missing, then mark this resolved.")}</p>
      )}
      {issue.detail && <p className="mt-2 whitespace-pre-line text-[14px] text-[#344054]" dir="auto">
        {issue.kind === "conflict" ? issue.detail.replace(/^Which value applies\?/, t("Which value applies?")) : issue.detail}</p>}
      {(issue.source_document || issue.page) && (
        <p className="mt-2 flex items-center gap-1 text-[12px] text-[#667085]">
          <FileText size={13} /> {issue.source_document || "-"}{issue.page ? ` · ${t("page")} ${issue.page}` : ""}
        </p>
      )}
      {withAnswer && (
        <div className="mt-3">
          <label className="text-[12px] font-semibold text-[#344054]" htmlFor={`ans-${issue.id}`}>{t("Answer / clarification")}</label>
          <textarea id={`ans-${issue.id}`} value={answer} onChange={(e) => setAnswer(e.target.value)} rows={2} maxLength={4000}
            placeholder={t("What the client answered, or what the team decided")}
            className="mt-1 w-full rounded-lg border border-[#d0d5dd] p-2 text-[14px] outline-none focus:border-[#162A4C]" />
        </div>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {withAnswer && (
          <button type="button" disabled={busy || answer === (issue.answer || "")} onClick={() => save({ answer })}
            className="rounded-lg border border-[#d0d5dd] px-3 py-1.5 text-[13px] font-semibold text-[#162A4C] disabled:opacity-40">{t("Save answer")}</button>
        )}
        {resolved ? (
          <button type="button" disabled={busy} onClick={() => save({ status: "OPEN" })}
            className="flex items-center gap-1 rounded-lg border border-[#d0d5dd] px-3 py-1.5 text-[13px] font-semibold text-[#344054] disabled:opacity-40">
            <RotateCcw size={13} /> {t("Reopen")}
          </button>
        ) : (
          <button type="button" data-testid="resolve-issue" disabled={busy}
            onClick={() => save(withAnswer ? { answer, status: "RESOLVED" } : { status: "RESOLVED" })}
            className="flex items-center gap-1 rounded-lg bg-[#162A4C] px-3 py-1.5 text-[13px] font-semibold text-white disabled:opacity-40">
            <CheckCircle2 size={13} /> {withAnswer ? t("Mark answered") : t("Mark reviewed")}
          </button>
        )}
        {issue.resolved_by && resolved && <span className="text-[12px] text-[#667085]">by {issue.resolved_by}</span>}
        {error && <span className="text-[12px] text-[#b42318]">{error}</span>}
      </div>
    </article>
  );
}

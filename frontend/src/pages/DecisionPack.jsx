import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Printer, ArrowLeft, FileSpreadsheet } from "lucide-react";
import apiClient from "../api/client";
import { usePrefs } from "../i18n";
import { ScoreBlock } from "../components/RecommendationPanel";
import { LABEL, tx } from "../components/BidTools";
import { WorkspaceLoading } from "../components/TenderLoading";

/** Stage 7 — decision pack: everything the authorised team needs, in one printable page.
 *  Certificates and approvals come first (do we need a partner?). Every fact shows its source;
 *  tags say what is FACT, CALCULATION or needs HUMAN REVIEW. The decision stays with the team. */

const TAG = { FACT: "bg-[#eef2f8] text-[#162A4C]", CALCULATION: "bg-[#f3eefb] text-[#5b3f8c]", REVIEW: "bg-[#fdf4de] text-[#8a6a22]" };
const CERT_STYLE = { MISSING: "bg-[#fdf0f0] text-[#b42318]", PARTNER_NEEDED: "bg-[#fdf4de] text-[#8a6a22]",
  CHECK: "bg-[#f2f4f7] text-[#475467]", HELD: "bg-[#e7f5ee] text-[#1f7a4d]" };
const CERT_LABEL = { MISSING: "Missing|cert", PARTNER_NEEDED: "Partner needed|cert", CHECK: "Check|cert", HELD: "Held|cert" };
const WHO = { bidder: "Company|who", partner: "Manufacturer / supplier / subcontractor|who", staff: "Staff|who", unclear: "Not stated|who" };
const AUDIT = {
  eligibility_override: "Continued despite the eligibility check", vote_saved: "Vote saved", vote_removed: "Vote removed",
  outcome_set: "Outcome set", task_done: "Task done", task_reopened: "Task reopened", checklist_item: "Checklist item updated",
  decision_override: "Decision overridden",
};

function Section({ n, title, tags = [], children, testid }) {
  const { t } = usePrefs();
  return (
    <section data-testid={testid} className="pack-section rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 className="text-[17px] font-bold text-[#101828]"><span className="me-2 text-[#98a2b3]">{n}</span>{title}</h2>
        {tags.map((k) => <span key={k} className={`rounded px-2 py-0.5 text-[11px] font-bold ${TAG[k]}`}>{t(k === "REVIEW" ? "Human review|tag" : k === "FACT" ? "Fact|tag" : "Calculation|tag")}</span>)}
      </div>
      {children}
    </section>
  );
}

const Src = ({ e }) => {
  const { t } = usePrefs();
  return e ? <span className="block text-[12px] text-[#667085]">{e.file} · {t("page")} {e.page}{e.quote ? ` — “${e.quote}”` : ""}</span> : null;
};

export default function DecisionPack() {
  const { tender_id: id } = useParams();
  const { t, lang } = usePrefs();
  const [p, setP] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { apiClient.getDecisionPack(id, lang).then(setP).catch((e) => setError(e.message)); }, [id, lang]);
  if (error) return <div data-testid="error-banner" className="m-8 rounded-xl border border-[#f5c6c6] bg-[#fdf0f0] p-4 text-[#a33a3a]">{error}</div>;
  if (!p) return <WorkspaceLoading />;
  const cs = p.certifications.summary;
  const c = p.compliance;
  const n = (() => { let i = 0; return () => ++i; })();
  return (
    <div data-testid="decision-pack" className="decision-pack mx-auto max-w-[980px] space-y-4 p-4 sm:p-6 lg:p-8">
      <div className="no-print flex flex-wrap items-center justify-between gap-2">
        <Link to={`/tenders/${encodeURIComponent(id)}`} className="flex items-center gap-1 text-[14px] font-semibold text-[#162A4C]"><ArrowLeft size={16} className="rtl:rotate-180" /> {t("Back to the tender")}</Link>
        <div className="flex gap-2">
          <a href={apiClient.complianceMatrixUrl(id, lang)} className="flex items-center gap-1.5 rounded-lg border border-[#162A4C] px-4 py-2 text-[14px] font-semibold text-[#162A4C]"><FileSpreadsheet size={15} /> {t("Compliance matrix (Excel)")}</a>
          <button type="button" onClick={() => window.print()} className="flex items-center gap-1.5 rounded-lg bg-[#162A4C] px-4 py-2 text-[14px] font-semibold text-white"><Printer size={15} /> {t("Print / save as PDF")}</button>
        </div>
      </div>

      <header className="pack-section rounded-2xl bg-[#162A4C] p-6 text-white">
        <p className="text-[13px] opacity-80">{t("Decision pack")}</p>
        <h1 className="mt-1 text-[24px] font-black">{p.tender.title || p.tender.id}</h1>
        <p className="mt-1 text-[13px] opacity-80">{[p.tender.id, p.tender.client, p.tender.location].filter(Boolean).join(" · ")} · {t("Prepared {date}", { date: new Date(p.generated_at).toLocaleString(lang === "ar" ? "ar-EG" : "en-GB") })}</p>
      </header>

      <Section n={n()} testid="pack-certs" title={t("Certificates and qualifications")} tags={["FACT", "REVIEW"]}>
        <p data-testid="pack-certs-summary" className={`mb-3 rounded-lg p-3 text-[14px] font-semibold ${cs.needs_partner ? "bg-[#fdf4de] text-[#8a6a22]" : "bg-[#e7f5ee] text-[#1f7a4d]"}`}>
          {p.certifications.items.length === 0 ? t("The tender asks for no specific certificates or approvals.")
            : cs.needs_partner ? t("A partner, supplier or certificate is needed: {m} missing, {p} to be covered by a manufacturer / supplier / subcontractor.", { m: cs.MISSING, p: cs.PARTNER_NEEDED })
              : t("No partner needed on certificates — {h} held, {c} to check.", { h: cs.HELD, c: cs.CHECK })}
        </p>
        <ul className="space-y-3">
          {p.certifications.items.map((it) => (
            <li key={`${it.name}-${it.who}`} className="text-[14px] text-[#344054]">
              <span className={`me-2 rounded px-2 py-0.5 text-[11px] font-bold ${CERT_STYLE[it.status]}`}>{t(CERT_LABEL[it.status])}</span>
              <b>{t(it.name)}</b> <span className="text-[12px] text-[#667085]">— {t("required from")}: {t(WHO[it.who])}{it.optional ? ` · ${t("optional")}` : ""}</span>
              {it.evidence.slice(0, 2).map((e, i) => <Src key={i} e={e} />)}
              {it.status === "PARTNER_NEEDED" && (
                <span className="block text-[12px] text-[#475467]">{t("Suggested from past tenders")}: {it.suggested?.length ? it.suggested.map((s) => s.contractor).join(t(", ")) : t("none recorded yet")}</span>
              )}
            </li>
          ))}
        </ul>
      </Section>

      <Section n={n()} testid="pack-eligibility" title={t("Eligibility check")} tags={["FACT"]}>
        {!p.eligibility || p.eligibility.status === "SKIPPED" || !p.eligibility.checks?.length
          ? <p className="text-[13px] text-[#667085]">{t("Not checked — fill Company capabilities in Settings.")}</p>
          : <ul className="space-y-1.5">{p.eligibility.checks.map((k) => (
            <li key={k.key} className="text-[13px] text-[#344054]"><b>{t(LABEL[k.result] || k.result)}</b> · {t(k.label)}: {tx(t, k.detail_key, k.detail_vars, k.detail)}<Src e={k.evidence} /></li>))}</ul>}
        {p.eligibility?.override_by && <p className="mt-2 text-[12px] text-[#8a6a22]">{t("Continued by {by}: {reason}", { by: p.eligibility.override_name || p.eligibility.override_by, reason: p.eligibility.override_reason || "" })}</p>}
      </Section>

      <Section n={n()} testid="pack-score" title={t("Go/No-Go score")} tags={["CALCULATION"]}>
        {p.score ? <ScoreBlock score={p.score} /> : <p className="text-[13px] text-[#667085]">{t("Not enough data yet to score this tender.")}</p>}
        {p.recommendation?.headline && <p className="mt-3 text-[14px] font-semibold text-[#101828]">{p.recommendation.headline}</p>}
      </Section>

      <Section n={n()} testid="pack-compliance" title={t("Compliance with mandatory requirements")} tags={["CALCULATION"]}>
        <p className="text-[14px] text-[#344054]">
          <b>{c.compliance_percent != null ? `${c.compliance_percent}%` : t("Not evaluated yet")}</b> · {t("{p} met, {f} contradicted, {r} to review, {x} without evidence — of {n} mandatory ({all} requirements in total).",
            { p: c.PASS, f: c.FAIL, r: c.REVIEW, x: c.MISSING_EVIDENCE, n: c.mandatory_total, all: c.total })}
        </p>
        <p className="mt-1 text-[12px] text-[#667085]">{t("Method: met mandatory requirements ÷ all mandatory requirements. Items to review or without evidence never count as met.")}</p>
        {p.gaps.length > 0 && (
          <ul className="mt-3 list-disc space-y-1 ps-5 text-[13px] text-[#344054]">
            {p.gaps.map((g) => <li key={g.requirement_id}>{g.requirement} <span className="text-[12px] text-[#667085]">({g.source_document} {g.page_or_section})</span></li>)}
          </ul>
        )}
      </Section>

      <Section n={n()} testid="pack-conflicts" title={t("Contradictions in the tender documents")} tags={["FACT", "REVIEW"]}>
        {p.conflicts.length === 0 ? <p className="text-[13px] text-[#667085]">{t("None found.")}</p> : (
          <ul className="space-y-3">{p.conflicts.map((x, i) => (
            <li key={i} className="text-[14px] text-[#344054]"><b>{t(x.label)}</b>
              {x.values.map((v, j) => <span key={j} className="block text-[13px]">{v.value} <Src e={v} /></span>)}
            </li>))}</ul>)}
      </Section>

      <Section n={n()} testid="pack-questions" title={t("Clarifications and missing documents")} tags={["REVIEW"]}>
        {[...p.questions, ...p.missing_documents].length === 0 ? <p className="text-[13px] text-[#667085]">{t("None open.")}</p> : (
          <ul className="space-y-2">{[...p.missing_documents, ...p.questions].map((q, i) => (
            <li key={i} className="text-[13px] text-[#344054]"><b>{t(q.title)}</b><span className="block whitespace-pre-line text-[12px] text-[#667085]">{q.detail}</span></li>))}</ul>)}
      </Section>

      <Section n={n()} testid="pack-checklist" title={t("Submission checklist")} tags={["FACT"]}>
        <p className="mb-2 text-[14px] text-[#344054]">{t("{r} of {n} ready, {x} not applicable.", { r: p.checklist.progress.READY, n: p.checklist.progress.total, x: p.checklist.progress.NOT_APPLICABLE })}</p>
        <ul className="space-y-1.5">{p.checklist.items.map((it) => (
          <li key={it.key} className="text-[13px] text-[#344054]"><b>{t({ TODO: "To do|cl", READY: "Ready|cl", NOT_APPLICABLE: "Not applicable|cl" }[it.status])}</b> · {it.quote}{it.assignee ? ` — ${it.assignee}` : ""}<span className="block text-[12px] text-[#667085]">{it.file} · {t("page")} {it.page}</span></li>))}</ul>
      </Section>

      <Section n={n()} testid="pack-votes" title={t("Department votes")} tags={["FACT"]}>
        {p.votes.votes.length === 0 ? <p className="text-[13px] text-[#667085]">{t("No department votes yet.")}</p> : (
          <>
            <p className="text-[14px] text-[#101828]"><b>{p.votes.summary.overall.approve_pct ?? "—"}%</b> {t("approve")} · {t("{a} approve, {r} reject, {x} abstain", { a: p.votes.summary.overall.approve, r: p.votes.summary.overall.reject, x: p.votes.summary.overall.abstain })}</p>
            <ul className="mt-1 text-[13px] text-[#475467]">{p.votes.votes.map((v) => <li key={v.member_name}>{v.member_name} ({t(v.department)}): {t(LABEL[v.vote])}{v.comment ? ` — ${v.comment}` : ""}</li>)}</ul>
          </>)}
      </Section>

      <Section n={n()} testid="pack-tasks" title={t("Team tasks")} tags={["FACT"]}>
        {p.tasks.length === 0 ? <p className="text-[13px] text-[#667085]">{t("No tasks yet.")}</p> : (
          <ul className="text-[13px] text-[#344054]">{p.tasks.map((x) => <li key={x.id}>{x.status === "DONE" ? "✓" : "○"} {x.title}{x.assignee ? ` — ${x.assignee}` : ""}{x.due_date ? ` · ${x.due_date}` : ""}</li>)}</ul>)}
      </Section>

      <Section n={n()} testid="pack-audit" title={t("Audit trail")} tags={["FACT"]}>
        {p.audit.length === 0 ? <p className="text-[13px] text-[#667085]">{t("No team actions recorded yet.")}</p> : (
          <ul className="space-y-1 text-[12px] text-[#475467]">{p.audit.map((e, i) => (
            <li key={i}>{e.at ? new Date(e.at).toLocaleString(lang === "ar" ? "ar-EG" : "en-GB") : ""} · <b>{t(AUDIT[e.action] || e.action)}</b>
              {e.actor_name ? ` · ${e.actor_name}` : ""}{e.actor ? ` (${e.actor})` : ""}
              {e.detail && Object.keys(e.detail).length ? ` — ${Object.entries(e.detail).map(([k, v]) => `${t(k)}: ${t(String((LABEL[v] || v) ?? "—"))}`).join(" · ")}` : ""}</li>))}</ul>)}
      </Section>

      <p className="pack-section rounded-xl border border-dashed border-[#d0d5dd] p-4 text-[13px] text-[#475467]">
        {t("This pack presents facts from the tender and your records, with their sources, and calculations with their method. The decision to bid belongs to the company's authorised team.")}
      </p>
    </div>
  );
}

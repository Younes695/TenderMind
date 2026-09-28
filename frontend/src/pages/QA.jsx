import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { MessageSquare } from "lucide-react";
import apiClient from "../api/client";
import IssueCard from "../components/IssueCard";
import { useT } from "../i18n";

/** Questions per tender: unclear wording, scanned pages that could not be read
 *  reliably, requirements the AI could not classify - each with an answer. */
export default function QA() {
  const t = useT();
  const [params, setParams] = useSearchParams();
  const [tenders, setTenders] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [show, setShow] = useState("OPEN");
  const tenderId = params.get("tender") || "";

  useEffect(() => {
    apiClient.listTenders()
      .then((list) => {
        const live = (list || []).filter((t) => t.id !== "SA-2018-HV2");
        setTenders(live);
        if (!params.get("tender") && live.length) setParams({ tender: live[0].id }, { replace: true });
      })
      .catch((e) => setError(e.message));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!tenderId) return;
    setData(null);
    apiClient.getTenderIssues(tenderId, { category: "question" }).then(setData).catch((e) => setError(e.message));
  }, [tenderId]);

  const visible = useMemo(() => (data?.issues || []).filter((i) => show === "ALL" || i.status === show), [data, show]);
  const onChange = (u) => setData((d) => ({ ...d, issues: d.issues.map((i) => (i.id === u.id ? u : i)) }));

  if (error) return <div data-testid="error-banner" className="m-8 rounded-xl border border-[#f5c6c6] bg-[#fdf0f0] p-4 text-[#a33a3a]">{error}</div>;
  if (!tenders) return <div className="p-8">{t("Loading…")}</div>;

  return (
    <div className="mx-auto max-w-[1100px] space-y-4 p-4 sm:p-6 lg:p-8">
      <div>
        <h1 className="flex items-center gap-2 text-[24px] font-black text-[#101828]"><MessageSquare size={22} /> {t("Q&A")}</h1>
        <p className="mt-1 text-[14px] text-[#667085]">{t("Unclear points found in the tender documents — ask the client, then record the answer.")}</p>
      </div>
      {tenders.length === 0 ? (
        <div data-testid="empty-state" className="rounded-xl border border-[#e8e4dc] bg-white p-6 text-[14px] text-[#667085]">{t("No tenders yet.")}</div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-[13px] font-semibold text-[#344054]" htmlFor="qa-tender">{t("Tender")}</label>
            <select id="qa-tender" value={tenderId} onChange={(e) => setParams({ tender: e.target.value })}
              className="rounded-lg border border-[#d0d5dd] bg-white px-3 py-2 text-[14px]">
              {tenders.map((t) => <option key={t.id} value={t.id}>{t.id}{t.title ? ` - ${t.title}` : ""}</option>)}
            </select>
            <div className="flex overflow-hidden rounded-lg border border-[#d0d5dd] text-[13px]" role="group" aria-label="Filter">
              {[["OPEN", t("Open")], ["RESOLVED", t("Answered")], ["ALL", t("All")]].map(([v, label]) => (
                <button key={v} type="button" onClick={() => setShow(v)}
                  className={`px-3 py-1.5 font-semibold ${show === v ? "bg-[#162A4C] text-white" : "bg-white text-[#344054]"}`}>{label}</button>
              ))}
            </div>
          </div>
          {!data ? <div className="p-2 text-[14px] text-[#667085]">{t("Loading questions…")}</div>
            : visible.length === 0 ? (
              <div data-testid="empty-state" className="rounded-xl border border-[#e8e4dc] bg-white p-6 text-[14px] text-[#667085]">
                {data.count === 0 ? t("No questions for this tender (process it first if it has not been analysed).") : t("Nothing in this filter.")}
              </div>
            ) : (
              <div className="space-y-3">{visible.map((i) => <IssueCard key={i.id} issue={i} withAnswer onChange={onChange} />)}</div>
            )}
        </>
      )}
    </div>
  );
}

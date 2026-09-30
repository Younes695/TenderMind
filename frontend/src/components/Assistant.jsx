import { useEffect, useRef, useState } from "react";
import { Link, useMatch } from "react-router-dom";
import { MessageCircleQuestion, X, Send } from "lucide-react";
import apiClient from "../api/client";
import { usePrefs, translate } from "../i18n";
import { tx } from "./BidTools";

/** Stage 8 — assistant panel. Answers come from the company's own records, with sources.
 *  On a tender page it knows which tender you mean. */

const ASK_GENERAL = ["What tasks are overdue?", "What are the upcoming deadlines?", "Which clients did we work with?"];
const ASK_TENDER = ["Is this tender suitable for us?", "Why is the recommendation what it is?",
  "Do we need a partner or certificates?", "Have we done something similar before?", "Did we work with this client before?",
  "What is still missing on the submission checklist?"];

function Answer({ a, onAsk }) {
  const prefs = usePrefs();
  // the answer follows the language of the question, not only the interface language
  const t = a.lang ? (key, vars) => translate(a.lang, key, vars) : prefs.t;
  return (
    <div dir={a.lang === "ar" ? "rtl" : a.lang === "en" ? "ltr" : undefined} className="space-y-1.5 text-[13px] text-[#344054]">
      {a.lines.map((l, i) => l.example ? (
        <button key={i} type="button" onClick={() => onAsk?.(t(l.key))}
          className="me-1.5 mt-1 inline-block rounded-full border border-[#d0d5dd] px-3 py-1 text-start text-[12px] text-[#162A4C] hover:border-[#162A4C]">{t(l.key)}</button>
      ) : (
        <p key={i} className="whitespace-pre-line">
          {l.text ? l.text : tx(t, l.key, l.vars)}
          {l.reason?.key && <span className="block text-[12px] text-[#667085]">{tx(t, l.reason.key, l.reason.vars)}</span>}
        </p>
      ))}
      {a.sources?.length > 0 && (
        <ol className="mt-2 list-decimal space-y-1 border-t border-[#eef0f3] ps-4 pt-2 text-[12px] text-[#667085]">
          {a.sources.map((s, i) => <li key={i}>{s.file} · {t("page")} {s.page}{s.quote ? ` — “${s.quote}”` : ""}</li>)}
        </ol>
      )}
      {a.links?.length > 0 && (
        <p className="flex flex-wrap gap-2 pt-1">{a.links.map((l, i) => <Link key={i} to={l.href} className="text-[12px] font-semibold text-[#162A4C] underline">{t(l.label)}</Link>)}</p>
      )}
    </div>
  );
}

export default function Assistant() {
  const { t, lang } = usePrefs();
  const m = useMatch("/tenders/:tender_id");
  const tenderId = m?.params?.tender_id && m.params.tender_id !== "new" ? m.params.tender_id : null;
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [chat, setChat] = useState([]);
  const [busy, setBusy] = useState(false);
  const end = useRef(null);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [chat, busy]);
  const ask = async (question) => {
    const text = (question || q).trim();
    if (!text || busy) return;
    setQ("");
    setChat((c) => [...c, { role: "user", text }]);
    setBusy(true);
    try {
      const a = await apiClient.askAssistant({ question: text, tender_id: tenderId, lang });
      setChat((c) => [...c, { role: "assistant", a }]);
    } catch (err) {
      setChat((c) => [...c, { role: "assistant", a: { lines: [{ text: err.message }] } }]);
    } finally { setBusy(false); }
  };
  const suggestions = tenderId ? ASK_TENDER : ASK_GENERAL;
  return (
    <>
      {!open && (
        <button type="button" data-testid="assistant-open" onClick={() => setOpen(true)}
          className="no-print fixed bottom-5 end-5 z-40 flex items-center gap-2 rounded-full bg-[#162A4C] px-4 py-3 text-[14px] font-semibold text-white shadow-lg">
          <MessageCircleQuestion size={18} /> {t("Ask TenderMind")}
        </button>
      )}
      {open && (
        <div role="dialog" aria-label={t("Assistant")} data-testid="assistant-panel"
          className="no-print fixed bottom-5 end-5 z-40 flex max-h-[75vh] w-[min(420px,calc(100vw-2.5rem))] flex-col rounded-2xl border border-[#e8e4dc] bg-white shadow-2xl">
          <div className="flex items-center justify-between border-b border-[#eef0f3] px-4 py-3">
            <div>
              <p className="text-[15px] font-bold text-[#101828]">{t("Ask TenderMind")}</p>
              <p className="text-[11px] text-[#667085]">{tenderId ? t("About tender {id}", { id: tenderId }) : t("About all your tenders")} · {t("answers come from your own records")}</p>
            </div>
            <button type="button" aria-label={t("Close")} onClick={() => setOpen(false)}><X size={18} /></button>
          </div>
          <div className="flex-1 space-y-3 overflow-auto px-4 py-3">
            {chat.length === 0 && (
              <div className="flex flex-wrap gap-2">
                {suggestions.map((s) => <button key={s} type="button" onClick={() => ask(t(s))}
                  className="rounded-full border border-[#d0d5dd] px-3 py-1.5 text-start text-[12px] text-[#344054] hover:border-[#162A4C]">{t(s)}</button>)}
              </div>
            )}
            {chat.map((m2, i) => m2.role === "user"
              ? <p key={i} className="ms-auto w-fit max-w-[85%] rounded-2xl bg-[#162A4C] px-3 py-2 text-[13px] text-white">{m2.text}</p>
              : <div key={i} className="max-w-[95%] rounded-2xl bg-[#faf9f6] px-3 py-2"><Answer a={m2.a} onAsk={ask} /></div>)}
            {busy && <p data-testid="assistant-busy" className="text-[12px] text-[#667085]">{t("Looking through your records…")}</p>}
            <span ref={end} />
          </div>
          <form onSubmit={(e) => { e.preventDefault(); ask(); }} className="flex gap-2 border-t border-[#eef0f3] p-3">
            <input data-testid="assistant-input" value={q} onChange={(e) => setQ(e.target.value)} maxLength={500}
              placeholder={t("Ask about your tenders…")} className="min-w-0 flex-1 rounded-lg border border-[#d0d5dd] px-3 py-2 text-[14px] outline-none focus:border-[#162A4C]" />
            <button type="submit" aria-label={t("Send")} disabled={busy || !q.trim()} className="rounded-lg bg-[#162A4C] px-3 text-white disabled:opacity-50"><Send size={16} className="rtl:rotate-180" /></button>
          </form>
        </div>
      )}
    </>
  );
}

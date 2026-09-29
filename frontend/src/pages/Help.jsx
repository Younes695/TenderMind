import { Link } from "react-router-dom";
import { LifeBuoy, Settings, Upload, ShieldCheck, ListChecks, Users, Gavel, FileText, MessageCircleQuestion } from "lucide-react";
import { usePrefs } from "../i18n";

/** Stage 9 — how to use TenderMind, step by step (both languages). */

const STEPS = [
  [Settings, "Set up your company once", "Settings: fill the company profile, capabilities (types of work, highest kV, countries, certifications, registrations), the tender team and the score weights. Upload company documents in Company Knowledge.", "/settings"],
  [Upload, "Upload a tender", "New Tender: give it an ID and title, upload all the files (PDF, Word, Excel, scans, ZIP/RAR) and start processing. Large packages are fine; processing resumes if the server restarts.", "/tenders/new"],
  [ShieldCheck, "Eligibility check first", "Before the full analysis the tender is compared with your capabilities. If it clearly does not fit, it stops and tells you why, with the page — you can continue anyway with a reason.", null],
  [ListChecks, "Read the tender in minutes", "On the tender page: the quick summary (client, dates, what you need to do), requirements with their page, certificates and whether you need a partner, contradictions in the documents, and questions for the tender owner with a ready email draft.", "/tenders"],
  [Users, "Work as a team", "Open 'Tender team & tools': RFP parts and suggested suppliers, the submission checklist, tasks with owners and due dates, department votes, notes and the stage and submission deadline. Reminders appear in Notifications.", null],
  [Gavel, "Decide", "The Go/No-Go score explains each factor. The Decision board compares all tenders; Approvals is where the tender manager records the final Go / No-Go with a reason. The decision is always your team's.", "/go-no-go"],
  [FileText, "Share the result", "Print the decision pack (certificates first) or save it as PDF, and download the compliance matrix in Excel for the bid.", null],
  [MessageCircleQuestion, "Ask TenderMind", "The assistant button on every page answers from your own records — overdue tasks, deadlines, why the recommendation, similar tenders, the client's history, certificates — and shows the source of each answer.", null],
];

export default function Help() {
  const { t } = usePrefs();
  return (
    <main data-testid="help" className="min-h-screen bg-[#f8f7f3] p-4 sm:p-6 lg:p-8">
      <div className="mx-auto max-w-[900px] space-y-4">
        <h1 className="flex items-center gap-2 text-[22px] font-black text-[#101828]"><LifeBuoy size={22} /> {t("Help")}</h1>
        <p className="text-[14px] text-[#667085]">{t("How to go from a tender package to a confident bid decision.")}</p>
        <ol className="space-y-3">
          {STEPS.map(([Icon, title, text, href], i) => (
            <li key={title} className="flex gap-4 rounded-2xl border border-[#e5e1d9] bg-white p-5">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#162A4C] text-[15px] font-black text-white">{i + 1}</span>
              <div>
                <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><Icon size={17} /> {t(title)}</h2>
                <p className="mt-1 text-[14px] leading-relaxed text-[#475467]">{t(text)}</p>
                {href && <Link to={href} className="mt-2 inline-block text-[13px] font-semibold text-[#162A4C] underline">{t("Open")}</Link>}
              </div>
            </li>
          ))}
        </ol>
        <p className="rounded-xl border border-dashed border-[#d0d5dd] p-4 text-[13px] text-[#475467]">
          {t("Something not working? Settings → Report a problem sends it straight to our team.")}
        </p>
      </div>
    </main>
  );
}

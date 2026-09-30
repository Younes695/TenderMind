import { Link } from "react-router-dom";
import { Radar, FileSearch, ShieldCheck, Boxes, Scale, Send } from "lucide-react";
import { useT } from "../i18n";

// The real workflow of the product, step by step — every step is a working feature.
const STEPS = [
  { icon: Radar, title: "Discover", text: "Tender Radar collects notices from public sources in Egypt and the GCC and shows a match % with the reasons for your company." },
  { icon: FileSearch, title: "Analyse", text: "Upload the RFP package (PDF, Word, Excel, scans, archives). Every requirement, date and clause is extracted with its file and page." },
  { icon: ShieldCheck, title: "Qualify", text: "The eligibility check compares the tender with your certificates, voltage, work types and countries, and shows what a partner must cover." },
  { icon: Boxes, title: "Price", text: "BOQ materials are priced from your own supplier price lists, and RFQ packages per equipment are generated for your suppliers." },
  { icon: Scale, title: "Decide", text: "The decision board, department votes and approvals end in a decision pack with every fact and its source. The decision stays with your team." },
  { icon: Send, title: "Submit", text: "The submission checklist, team tasks, reminders and the compliance matrix keep the bid on time." },
];

export default function HowItWorks() {
  const t = useT();
  return (
    <section className="bg-[#f5f3ee] px-4 py-14 sm:py-16">
      <div className="mx-auto max-w-[1100px]">
        <h1 className="text-center text-[32px] font-bold text-[#162A4C] sm:text-[38px]">{t("How TenderMind works")}</h1>
        <p className="mx-auto mt-3 max-w-[640px] text-center text-[15px] text-[#4b5f86]">{t("From the first notice to a submitted bid, in six steps.")}</p>
        <ol className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map(({ icon: Icon, title, text }, i) => (
            <li key={title} className="rounded-2xl border border-[#ebe8e1] bg-white p-6">
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#162A4C] text-[14px] font-bold text-white">{i + 1}</span>
                <Icon size={20} className="text-[#C8A96B]" />
                <h2 className="text-[17px] font-bold text-[#162A4C]">{t(title)}</h2>
              </div>
              <p className="mt-3 text-[14px] leading-relaxed text-[#4b5f86]">{t(text)}</p>
            </li>
          ))}
        </ol>
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          <Link to="/signup" className="rounded-lg bg-[#162A4C] px-6 py-3 text-[14px] font-bold text-white">{t("Start Trial")}</Link>
          <Link to="/demo" className="rounded-lg border-2 border-[#162A4C] px-6 py-3 text-[14px] font-bold text-[#162A4C]">{t("Book a Demo")}</Link>
        </div>
      </div>
    </section>
  );
}

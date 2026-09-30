import { Link } from "react-router-dom";
import { Radar, FileSearch, ShieldCheck, Boxes, PackageOpen, Scale, MessageCircleQuestion, Lock } from "lucide-react";
import { useT } from "../i18n";

// The product itself: the modules that exist in TenderMind today.
const MODULES = [
  { icon: Radar, title: "Tender Radar", text: "Notices from public sources in Egypt and the GCC, each with a match % and the reasons for your company." },
  { icon: FileSearch, title: "RFP analysis", text: "Every requirement, date and clause extracted from PDF, Word, Excel, scans and archives, with its file and page." },
  { icon: ShieldCheck, title: "Eligibility check", text: "Your certificates, voltage, work types and countries against the tender, with an eligibility % and what a partner must cover." },
  { icon: Boxes, title: "BOQ materials & prices", text: "Materials read from the bill of quantities and priced from your own supplier price lists, with the same material across all active tenders." },
  { icon: PackageOpen, title: "RFQ packages", text: "One request for quotation per equipment package, with the scope pages, design criteria, drawings and data schedules, ready as a ZIP." },
  { icon: Scale, title: "Decision pack", text: "Decision board, department votes and approvals, ending in a pack with every fact and its source and a summary for management." },
  { icon: MessageCircleQuestion, title: "Ask TenderMind", text: "An assistant that answers in Arabic or English from your tender documents only, always citing the file and page." },
  { icon: Lock, title: "Security", text: "Each account sees only its own tenders, every action is logged, and enterprises can run TenderMind on their own servers." },
];

export default function Product() {
  const t = useT();
  return (
    <section className="bg-[#f5f3ee] px-4 py-14 sm:py-16">
      <div className="mx-auto max-w-[1100px]">
        <h1 className="text-center text-[32px] font-bold text-[#162A4C] sm:text-[38px]">{t("One platform for the whole tender")}</h1>
        <p className="mx-auto mt-3 max-w-[680px] text-center text-[15px] text-[#4b5f86]">
          {t("TenderMind reads the tender, checks if you qualify, prepares pricing and supplier RFQs, and gives management an evidence-based decision.")}
        </p>
        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {MODULES.map(({ icon: Icon, title, text }) => (
            <article key={title} className="rounded-2xl border border-[#ebe8e1] bg-white p-5">
              <Icon size={22} className="text-[#C8A96B]" />
              <h2 className="mt-3 text-[16px] font-bold text-[#162A4C]">{t(title)}</h2>
              <p className="mt-2 text-[13px] leading-relaxed text-[#4b5f86]">{t(text)}</p>
            </article>
          ))}
        </div>
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          <Link to="/how-it-works" className="rounded-lg border-2 border-[#162A4C] px-6 py-3 text-[14px] font-bold text-[#162A4C]">{t("See How It Works")}</Link>
          <Link to="/demo" className="rounded-lg bg-[#162A4C] px-6 py-3 text-[14px] font-bold text-white">{t("Book a Demo")}</Link>
        </div>
      </div>
    </section>
  );
}

import { Link } from "react-router-dom";
import { Hourglass } from "lucide-react";
import { useT } from "../i18n";

// Placeholder for sidebar sections that are planned but not built yet, so the
// link lands on an honest page instead of a blank screen.
function ComingSoon({ title, description }) {
  const t = useT();
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-[640px] flex-col items-center justify-center p-6 text-center" data-testid="coming-soon">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#eef2f8] text-[#162A4C]">
        <Hourglass size={26} />
      </span>
      <h1 className="mt-4 text-[22px] font-black text-[#101828]">{t(title)}</h1>
      <p className="mt-2 text-[14px] leading-relaxed text-[#667085]">{t(description)}</p>
      <span className="mt-4 rounded-full bg-[#fdf4de] px-3 py-1 text-[12px] font-bold text-[#a98238]">{t("Coming soon")}</span>
      <div className="mt-6 flex gap-3">
        <Link to="/tenders" className="rounded-xl border border-[#d0d5dd] bg-white px-4 py-2 text-[14px] font-semibold text-[#162A4C]">{t("View tenders")}</Link>
        <Link to="/dashboard" className="rounded-xl bg-[#162A4C] px-4 py-2 text-[14px] font-semibold text-white">{t("Back to dashboard")}</Link>
      </div>
    </div>
  );
}

export default ComingSoon;

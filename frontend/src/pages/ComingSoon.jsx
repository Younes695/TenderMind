import { Link } from "react-router-dom";
import { Hourglass } from "lucide-react";

// Placeholder for sidebar sections that are planned but not built yet, so the
// link lands on an honest page instead of a blank screen.
function ComingSoon({ title, description }) {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-[640px] flex-col items-center justify-center p-6 text-center" data-testid="coming-soon">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#eef2f8] text-[#162A4C]">
        <Hourglass size={26} />
      </span>
      <h1 className="mt-4 text-[22px] font-black text-[#101828]">{title}</h1>
      <p className="mt-2 text-[14px] leading-relaxed text-[#667085]">{description}</p>
      <span className="mt-4 rounded-full bg-[#fdf4de] px-3 py-1 text-[12px] font-bold text-[#a98238]">Coming soon</span>
      <div className="mt-6 flex gap-3">
        <Link to="/tenders" className="rounded-xl border border-[#d0d5dd] bg-white px-4 py-2 text-[14px] font-semibold text-[#162A4C]">View tenders</Link>
        <Link to="/dashboard" className="rounded-xl bg-[#162A4C] px-4 py-2 text-[14px] font-semibold text-white">Back to dashboard</Link>
      </div>
    </div>
  );
}

export default ComingSoon;

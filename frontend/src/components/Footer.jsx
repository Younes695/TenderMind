
const footerCols = [
  { title: "Product", links: [["Tender Analysis", "/how-it-works"], ["Go / No-Go", "/how-it-works"], ["Subcontractor RFQs", "/how-it-works"], ["Pricing", "/pricing"]] },
  { title: "Solutions", links: [["Tender Managers", "/solutions"], ["Finance", "/solutions"], ["Executives", "/solutions"], ["Industries", "/industries"]] },
  { title: "Company", links: [["Book a Demo", "/demo"], ["Log in", "/login"], ["Sign up", "/signup"]] },
  { title: "Compliance", links: [["Security", "/security"], ["Audit Logs", "/security"], ["On-premise option", "/demo?topic=plan:enterprise"]] },
];

import { Link } from "react-router-dom";
import { useT } from "../i18n";

function Footer (){
    const t = useT();
    return(
        <>
              <footer className="bg-[#0F1D38] px-4 py-12 sm:px-6">
        <div className="mx-auto max-w-[1240px]">
          <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[1.6fr_repeat(4,1fr)]">
            <div>
              <p className="mb-3 text-[16px] font-extrabold tracking-wide text-white">{t("TENDERMIND")}</p>
              <p className="mb-3 max-w-[280px] text-[13px] leading-relaxed text-[#a9b8d4]">
                {t("From RFP to Ready-to-Bid. AI-powered tender intelligence for teams that can't afford to miss the details.")}
              </p>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[#C8A96B]">
                {t("Egypt · GCC")}
              </p>
            </div>
            {footerCols.map(({ title, links }) => (
              <div key={title}>
                <p className="mb-3 text-[12px] font-semibold tracking-wide text-[#a9b8d4]">{t(title)}</p>
                <ul className="space-y-2.5">
                  {links.map(([l, to]) => (
                    <li key={l}>
                      <Link to={to} className="text-[13px] text-white/90 transition hover:text-[#C8A96B]">
                        {t(l)}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="mt-10 flex flex-col justify-between gap-2 border-t border-white/10 pt-6 text-[12px] text-[#8394b3] sm:flex-row">
            <p>{t("© 2026 TenderMind. All rights reserved.")}</p>
            <p>{t("Understand the tender. Decide with confidence. Coordinate the team. Submit on time.")}</p>
          </div>
        </div>
      </footer></>
    );
}
export default Footer ;
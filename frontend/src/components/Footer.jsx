
const footerCols = [
  { title: "Product", links: ["Tender Analysis", "Go / No-Go", "Financial Intelligence", "Approvals", "Subcontractor RFQs"] },
  { title: "Solutions", links: ["Tender Managers", "Finance", "Executives", "Technical Teams", "Procurement"] },
  { title: "Company", links: ["About", "Security", "Pricing", "Contact", "Careers"] },
  { title: "Compliance", links: ["Role-Based Access", "Audit Logs", "Data Residency (KSA)", "Privacy", "Terms"] },
];


function Footer (){
    return(
        <>
              <footer className="bg-[#0F1D38] px-4 py-12 sm:px-6">
        <div className="mx-auto max-w-[1240px]">
          <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[1.6fr_repeat(4,1fr)]">
            <div>
              <p className="mb-3 text-[16px] font-extrabold tracking-wide text-white">TENDERMIND</p>
              <p className="mb-3 max-w-[280px] text-[13px] leading-relaxed text-[#a9b8d4]">
                From RFP to Ready-to-Bid. AI-powered tender intelligence for teams that can’t afford to miss the details.
              </p>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[#C8A96B]">
                Riyadh · Dubai · Cairo
              </p>
            </div>
            {footerCols.map(({ title, links }) => (
              <div key={title}>
                <p className="mb-3 text-[12px] font-semibold tracking-wide text-[#a9b8d4]">{title}</p>
                <ul className="space-y-2.5">
                  {links.map((l) => (
                    <li key={l}>
                      <a href="#" className="text-[13px] text-white/90 transition hover:text-[#C8A96B]">
                        {l}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="mt-10 flex flex-col justify-between gap-2 border-t border-white/10 pt-6 text-[12px] text-[#8394b3] sm:flex-row">
            <p>© 2026 TenderMind. All rights reserved.</p>
            <p>Understand the tender. Decide with confidence. Coordinate the team. Submit on time.</p>
          </div>
        </div>
      </footer></>
    );
}
export default Footer ;
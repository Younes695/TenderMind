import {
  ClipboardList,
  Briefcase,
  Wallet,
  Crown,
  Users,
  ShoppingCart,
} from "lucide-react";

const personas = [
  {
    icon: ClipboardList,
    title: "Tender Managers",
    problem: "Owning deadlines across five disconnected tools.",
    help: "One pipeline with decomposition, tasks, Q&A and readiness in a single view.",
    tags: ["RFP Decomposition", "Tasks & Deadlines", "Submission Readiness"],
  },
  {
    icon: Briefcase,
    title: "Business Development",
    problem: "Chasing tenders without knowing which are winnable.",
    help: "Match scores and Go / No-Go rationale before BD spends a day on pursuit.",
    tags: ["Match Scoring", "Go / No-Go", "Analytics"],
  },
  {
    icon: Wallet,
    title: "Finance",
    problem: "Asked to approve bids without cash-flow visibility.",
    help: "Payment terms, retention and bonds modelled with exposure charts.",
    tags: ["Cash Flow Analysis", "Risk Flags", "Approval Gate"],
  },
  {
    icon: Crown,
    title: "Executives",
    problem: "Board decisions on bids with incomplete information.",
    help: "Board-ready decision cards with evidence, risk and human accountability.",
    tags: ["Decision Cards", "Audit Logs", "Portfolio Analytics"],
  },
  {
    icon: Users,
    title: "Technical Teams",
    problem: "Reading 300-page RFPs to find their ten pages.",
    help: "Only relevant sections routed per discipline with clear owners.",
    tags: ["Work Packages", "Requirements", "Q&A"],
  },
  {
    icon: ShoppingCart,
    title: "Procurement",
    problem: "Subcontractor quotes arriving late and incomparable.",
    help: "Structured RFQs with side-by-side price and technical comparison.",
    tags: ["Subcontractor RFQs", "Comparison", "Selection Audit"],
  },
];

function Solutions() {
  return (
    <>
      {/* Hero band */}
      <section className="bg-[#162A4C] py-14 sm:py-16">
        <div className="mx-auto max-w-[1190px] px-4 sm:px-6 lg:px-8">
          <h1 className="mb-4 max-w-[640px] text-[32px] font-bold leading-tight tracking-tight text-white sm:text-[38px]">
            Built for every seat at the bid table.
          </h1>
          <p className="max-w-[560px] text-[14px] leading-relaxed text-[#c5d0e6]">
            Each persona gets its own view — all reading from the same
            tender truth.
          </p>
        </div>
      </section>

      {/* Persona cards */}
      <section className="bg-[#f5f3ee] py-10 sm:py-14">
        <div className="mx-auto grid max-w-[1190px] grid-cols-1 gap-4 px-4 sm:grid-cols-2 sm:px-6 lg:grid-cols-3 lg:px-8">
          {personas.map(({ icon: Icon, title, problem, help, tags }) => (
            <article
              key={title}
              className="rounded-2xl border border-[#ebe8e1] bg-white p-5"
            >
              <span className="mb-4 inline-flex h-9 w-9 items-center justify-center rounded-lg bg-[#eef0f4] text-[#162A4C]">
                <Icon size={17} strokeWidth={1.8} />
              </span>
              <h3 className="mb-3 text-[15px] font-bold text-[#162A4C]">
                {title}
              </h3>

              <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-[#c0453f]">
                Problem
              </p>
              <p className="mb-3 text-[13px] leading-relaxed text-[#4b5f86]">
                {problem}
              </p>

              <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-emerald-700">
                How TenderMind Helps
              </p>
              <p className="mb-4 text-[13px] leading-relaxed text-[#4b5f86]">
                {help}
              </p>

              <div className="flex flex-wrap gap-2">
                {tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-md bg-[#eef0f4] px-2.5 py-1 text-[11px] font-medium text-[#162A4C]"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

export default Solutions;
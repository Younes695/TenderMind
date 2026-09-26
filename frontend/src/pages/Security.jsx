import {
  KeyRound,
  ScrollText,
  FileLock2,
  History,
  GitBranch,
  FileCog,
  Info,
} from "lucide-react";

const controls = [
  {
    icon: KeyRound,
    title: "Role-Based Access",
    text: "Tender-level permissions for owners, reviewers and viewers.",
  },
  {
    icon: ScrollText,
    title: "Audit Logs",
    text: "Every view, edit, approval and export recorded with timestamps.",
  },
  {
    icon: FileLock2,
    title: "Document Permissions",
    text: "Granular access per file, package and subcontractor share.",
  },
  {
    icon: History,
    title: "Approval History",
    text: "Immutable chain from request to board sign-off.",
  },
  {
    icon: GitBranch,
    title: "Version Control",
    text: "Every RFP revision diffed; analysis re-runs on change.",
  },
  {
    icon: FileCog,
    title: "Secure Document Handling",
    text: "Encryption in transit and at rest; KSA data residency.",
  },
];

function Security() {
  return (
    <>
      {/* Hero band */}
      <section className="bg-[#162A4C] py-14 sm:py-16">
        <div className="mx-auto max-w-[1190px] px-4 sm:px-6 lg:px-8">
          <span className="mb-3 block text-[11px] font-semibold uppercase tracking-widest text-[#C8A96B]">
            Security & Control
          </span>
          <h1 className="mb-4 max-w-[560px] text-[32px] font-bold leading-tight tracking-tight text-white sm:text-[38px]">
            Your tenders contain sensitive information. We treat them that
            way.
          </h1>
          <p className="max-w-[560px] text-[14px] leading-relaxed text-[#c5d0e6]">
            Enterprise controls for who sees what, who approved what, and
            when — on every tender.
          </p>
        </div>
      </section>

      {/* Controls grid + note + CTA */}
      <section className="bg-[#f5f3ee] py-10 sm:py-14">
        <div className="mx-auto max-w-[1190px] px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {controls.map(({ icon: Icon, title, text }) => (
              <article
                key={title}
                className="rounded-2xl border border-[#ebe8e1] bg-white p-5"
              >
                <span className="mb-4 inline-flex h-9 w-9 items-center justify-center rounded-lg bg-[#eef0f4] text-[#162A4C]">
                  <Icon size={17} strokeWidth={1.8} />
                </span>
                <h3 className="mb-1.5 text-[15px] font-bold text-[#162A4C]">
                  {title}
                </h3>
                <p className="text-[13px] leading-relaxed text-[#4b5f86]">
                  {text}
                </p>
              </article>
            ))}
          </div>

          <div className="mt-6 flex items-start gap-3 rounded-xl border border-[#eddcae] bg-[#f8efd6] px-5 py-4">
            <Info size={16} strokeWidth={1.8} className="mt-0.5 shrink-0 text-[#a88645]" />
            <p className="text-[13px] leading-relaxed text-[#7a5f2b]">
              Certification roadmap (ISO 27001, SOC 2) available under NDA
              during enterprise evaluation. No unsupported claims are made
              on this page.
            </p>
          </div>

          <div className="mt-8 flex justify-center">
            <button
              type="button"
              className="rounded-lg bg-[#162A4C] px-6 py-3.5 text-[14px] font-bold text-white transition-colors hover:bg-[#0F1D38]"
            >
              Explore Security with our team
            </button>
          </div>
        </div>
      </section>
    </>
  );
}

export default Security;
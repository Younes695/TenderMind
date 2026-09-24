import {
  CheckCircle2,
  Layers,
  FolderOpen,
  ListChecks,
  Users,
} from "lucide-react";

const stats = [
  {
    label: "FINANCIAL RISK",
    value: "HIGH",
    valueColor: "text-[#C84A4A]",
    note: "Cash exposure –3.1M",
  },
  {
    label: "Q&A DEADLINE",
    value: "6 Days",
    valueColor: "text-[#a98238]",
    note: "Due 02 Oct · 6 open",
  },
  {
    label: "APPROVALS",
    value: "Finance Review",
    valueColor: "text-[#162A4C]",
    note: "S. Haddad · due Sep 25",
  },
  {
    label: "SUBMISSION READINESS",
    value: "64%",
    valueColor: "text-[#162A4C]",
    note: "4 of 9 checks left",
  },
];

const modules = [
  { icon: Layers, value: "6", label: "Work Packages" },
  { icon: FolderOpen, value: "14", label: "Documents" },
  { icon: ListChecks, value: "23", label: "Tasks" },
  { icon: Users, value: "9", label: "Team" },
];

function TenderWorkspace() {
  return (
    <div className="min-h-screen bg-[#f8f7f3] p-4 sm:p-6 lg:p-8">
      <div className="mx-auto max-w-[1450px]">
        {/* Success banner */}
        <div className="flex items-center gap-3 rounded-xl border border-[#bcd8c6] bg-[#e7f2ec] px-5 py-4">
          <CheckCircle2 size={22} className="shrink-0 text-[#2E7D5B]" />
          <p className="text-[15px] font-medium text-[#2E7D5B] sm:text-[16px]">
            Tender Workspace created — RUH-2026-184 is ready for your team.
          </p>
        </div>

        {/* Title */}
        <div className="mt-6">
          <h1 className="text-[26px] font-black leading-tight text-[#101828] sm:text-[32px]">
            RUH-2026-184{" "}
            <span className="font-medium text-[#667085]">
              · <span className="text-[20px] sm:text-[24px]">Riyadh Smart Infrastructure</span>
            </span>
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
            <span className="rounded-lg border border-[#e6d3a3] bg-[#fdf4de] px-3 py-1.5 text-[14px] font-bold text-[#a98238] sm:text-[15px]">
              CONDITIONAL GO · 82 / 100
            </span>
            <span className="text-[14px] text-[#667085] sm:text-[16px]">
              18 Days Remaining • Submission 18 Oct 2026
            </span>
          </div>
        </div>

        {/* Main stats */}
        <section className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:gap-5 xl:grid-cols-4">
          {stats.map((s) => (
            <div
              key={s.label}
              className="rounded-2xl border border-[#e5e1d9] bg-white p-5 sm:p-6"
            >
              <p className="text-[13px] font-bold tracking-wide text-[#667085] sm:text-[14px]">
                {s.label}
              </p>
              <p className={`mt-2 text-[26px] font-black leading-none sm:text-[30px] ${s.valueColor}`}>
                {s.value}
              </p>
              <p className="mt-2 text-[14px] text-[#667085] sm:text-[15px]">{s.note}</p>
            </div>
          ))}
        </section>

        {/* Modules */}
        <section className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:gap-5 xl:grid-cols-4">
          {modules.map(({ icon: Icon, value, label }) => (
            <div
              key={label}
              className="flex items-center gap-4 rounded-2xl border border-[#e5e1d9] bg-white p-5 sm:p-6"
            >
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[#f3eee2] text-[#162A4C]">
                <Icon size={23} strokeWidth={1.8} />
              </span>
              <div>
                <p className="text-[24px] font-black leading-none text-[#101828]">{value}</p>
                <p className="mt-1.5 text-[14px] text-[#667085] sm:text-[15px]">{label}</p>
              </div>
            </div>
          ))}
        </section>

        {/* Actions */}
        <div className="mt-5 flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            className="flex h-[54px] items-center justify-center rounded-xl bg-[#162A4C] px-8 text-[16px] font-bold text-white transition-colors hover:bg-[#0F1D38]"
          >
            Open Command Center
          </button>
          <button
            type="button"
            className="flex h-[54px] items-center justify-center rounded-xl border border-[#e2e6ee] bg-white px-8 text-[16px] font-bold text-[#101828] transition-colors hover:bg-[#f5f6f9]"
          >
            Invite Team
          </button>
        </div>
      </div>
    </div>
  );
}

export default TenderWorkspace;

import { useState, useEffect } from "react";
import HeroHome from "../components/HeroHome";
import {
  FileWarning,
  LayoutGrid,
  Workflow,
  Timer,
  MailOpen,
  Sparkles,
  ShieldCheck,
  Wallet,
  Users,
  MessageSquare,
  Truck,
  FileSignature,
  Stamp,
  Send,
  ChevronRight,
  CheckCircle2,
  Check,
  AlertTriangle,
  Lock,
  FileText,
  Network,
  FileSearch,
  Scale,
  TrendingUp,
  ListChecks,
  Database,
  ScrollText,
  BarChart3,
  ArrowUp,
} from "lucide-react";

const industries = [
  "Construction",
  "Engineering",
  "Technology",
  "Infrastructure",
  "Government Contracting",
];

const problems = [
  {
    icon: FileWarning,
    title: "Missed requirements",
    text: "Important requirements are buried across hundreds of pages.",
  },
  {
    icon: LayoutGrid,
    title: "Manual Go / No-Go",
    text: "Decisions depend on spreadsheets, emails, and scattered opinions.",
  },
  {
    icon: Workflow,
    title: "Slow coordination",
    text: "Technical, finance, legal, and subcontractors work across disconnected workflows.",
  },
  {
    icon: Timer,
    title: "Deadline pressure",
    text: "Critical approvals and documents are often handled at the last minute.",
  },
];

const steps = [
  { icon: MailOpen, label: "RFP Received" },
  { icon: Sparkles, label: "AI Analysis" },
  { icon: ShieldCheck, label: "Go / No-Go" },
  { icon: Wallet, label: "Financial Review" },
  { icon: Users, label: "Team Assignment" },
  { icon: MessageSquare, label: "Q&A" },
  { icon: Truck, label: "Subcontractor RFQs" },
  { icon: FileSignature, label: "Proposal Preparation" },
  { icon: Stamp, label: "Approvals" },
  { icon: Send, label: "Submission" },
];

const capabilities = [
  "Company capabilities",
  "Past projects",
  "Certifications",
  "Financial policies",
  "Risk policies",
  "Capacity & strategy",
];

const scores = [
  { label: "Technical Fit", value: 92 },
  { label: "Financial Fit", value: 68 },
  { label: "Risk", value: 74 },
  { label: "Evaluation Fit", value: 88 },
  { label: "Capacity", value: 80 },
];

const reasons = [
  { ok: true, text: "Strong technical experience" },
  { ok: true, text: "Required certifications available" },
  { ok: false, text: "Payment terms exceed policy" },
  { ok: false, text: "High performance guarantee" },
];

const finStats = [
  { label: "Contract Value", value: "SAR 12.5M" },
  { label: "Payment Terms", value: "90 Days" },
  { label: "Retention", value: "10%" },
  { label: "Performance Bond", value: "10%" },
];

// height (%) per month; color is decided by index: 0-2 outflow, 3-6 peak, 7+ recovery
const cashBars = [27, 37, 51, 70, 88, 100, 90, 70, 52, 40, 32, 22];
const barColor = (i) =>
  i < 3 ? "bg-[#162A4C]" : i < 7 ? "bg-[#D06A68]" : "bg-[#C8A96B]";

const disciplines = ["Technical", "Mechanical", "Electrical", "Legal", "Finance", "Commercial"];

const approvals = [
  { name: "Tender Manager", status: "Approved", done: true },
  { name: "Finance Manager", status: "Approved", done: true },
  { name: "Collections", status: "In review", n: 3 },
  { name: "CEO", n: 4 },
  { name: "Board", n: 5 },
];

const rfqSteps = [
  "Generate RFQ",
  "Send to Contractors",
  "Receive Quotations",
  "Compare Prices & Fit",
  "Select Best Option",
];

const securityItems = [
  "Role-Based Access",
  "Audit Logs",
  "Document Permissions",
  "Approval History",
  "Version Control",
  "Secure Document Handling",
];

const auditLog = [
  "[09:41:02] finance.review opened RUH-2026-184",
  "[09:42:17] ai.analysis completed · 248 clauses",
  "[09:44:03] approval requested   Finance Manager",
];

const features = [
  { icon: FileSearch, title: "AI RFP Analysis", text: "248 requirements extracted in minutes, every clause linked to its page." },
  { icon: Scale, title: "Go / No-Go Intelligence", text: "Weighted scoring across technical, financial, risk and capacity." },
  { icon: TrendingUp, title: "Financial & Cash Flow Analysis", text: "Payment terms, retention and bonds modelled before you bid." },
  { icon: AlertTriangle, title: "Risk Analysis", text: "Contractual and commercial risks flagged with evidence." },
  { icon: ListChecks, title: "Evaluation Criteria Extraction", text: "Know exactly how the client will score your proposal." },
  { icon: Network, title: "RFP Decomposition", text: "One RFP split into owned work packages per discipline." },
  { icon: Users, title: "Team Collaboration", text: "Technical, finance and legal work from one source of truth." },
  { icon: Stamp, title: "Approval Workflows", text: "Documented chain from manager to board with timestamps." },
  { icon: MessageSquare, title: "Q&A Management", text: "Clarifications tracked against the Q&A deadline." },
  { icon: Truck, title: "Subcontractor RFQs", text: "Turn work packages into priced RFQs in one click." },
  { icon: Database, title: "Company Knowledge Base", text: "Capabilities, certs and past projects reused automatically." },
  { icon: FileSignature, title: "Proposal Workspace", text: "Structured writing mapped to evaluation criteria." },
  { icon: Send, title: "Submission Readiness", text: "Completeness checklist so nothing ships late." },
  { icon: ScrollText, title: "Audit Logs", text: "Every view, edit and approval recorded." },
  { icon: BarChart3, title: "Analytics", text: "Win rates, cycle times and pipeline by sector." },
];

const footerCols = [
  { title: "Product", links: ["Tender Analysis", "Go / No-Go", "Financial Intelligence", "Approvals", "Subcontractor RFQs"] },
  { title: "Solutions", links: ["Tender Managers", "Finance", "Executives", "Technical Teams", "Procurement"] },
  { title: "Company", links: ["About", "Security", "Pricing", "Contact", "Careers"] },
  { title: "Compliance", links: ["Role-Based Access", "Audit Logs", "Data Residency (KSA)", "Privacy", "Terms"] },
];

function Home() {
  const [showTop, setShowTop] = useState(false);

  useEffect(() => {
    const onScroll = () => setShowTop(window.scrollY > 400);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <>
      <HeroHome />

      {/* Logos + Problems */}
      <section className="bg-[#f5f3ee] px-4 py-10 sm:px-6 sm:py-14">
        <div className="mx-auto max-w-[1240px]">
          <p className="mb-4 text-center text-[13px] text-[#4b5f86]">
            Built for teams where every tender matters.
          </p>

          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {industries.map((name) => (
              <li
                key={name}
                className="flex flex-col gap-1.5 rounded-[10px] border border-[#ebe8e1] bg-white px-2 py-4 text-center"
              >
                <span className="text-[11px] text-[#4b5f86]">
                  Your Company Logo
                </span>
                <strong className="text-[13px] text-[#162A4C]">{name}</strong>
              </li>
            ))}
          </ul>

          <h2 className="mb-6 mt-12 max-w-[520px] text-[28px] font-bold leading-snug tracking-tight text-[#162A4C] sm:mt-[72px]">
            Your team shouldn’t spend hours deciding whether a tender is worth
            pursuing.
          </h2>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {problems.map(({ icon: Icon, title, text }) => (
              <article
                key={title}
                className="min-h-[150px] rounded-xl border border-[#ebe8e1] bg-white p-4"
              >
                <span className="mb-3.5 inline-flex h-[30px] w-[30px] items-center justify-center rounded-lg bg-[#eef0f4] text-[#162A4C]">
                  <Icon size={16} strokeWidth={1.8} />
                </span>
                <h3 className="mb-1.5 text-[12px] font-bold uppercase tracking-wide text-[#C8A96B]">
                  {title}
                </h3>
                <p className="text-[13px] leading-relaxed text-[#4b5f86]">
                  {text}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* One system */}
      <section className="bg-white px-4 py-10 sm:px-6 sm:py-14">
        <div className="mx-auto max-w-[1240px]">
          <span className="mb-2 block text-[11px] font-semibold uppercase tracking-widest text-[#C8A96B]">
            One system
          </span>
          <h2 className="mb-5 text-[28px] font-bold leading-snug tracking-tight text-[#162A4C]">
            One system from RFP to submission.
          </h2>

          <ol className="flex items-stretch overflow-x-auto pb-2">
            {steps.map(({ icon: Icon, label }, i) => (
              <li key={label} className="flex flex-1 shrink-0 items-center">
                <div className="flex h-[100px] w-[100px] flex-col items-center justify-center gap-1.5 rounded-xl border border-[#ebe8e1] bg-[#f5f3ee] px-1.5 py-2 text-center text-[#162A4C]">
                  <Icon size={20} strokeWidth={1.8} />
                  <span className="text-[12px] font-bold leading-tight">
                    {label}
                  </span>
                  <span className="text-[12px] text-[#C8A96B]">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                </div>
                {i < steps.length - 1 && (
                  <ChevronRight
                    size={16}
                    aria-hidden="true"
                    className="mx-1 shrink-0 text-[#9aa5bd]"
                  />
                )}
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* AI Intelligence + Go / No-Go */}
      <section className="bg-[#f5f3ee] px-4 py-10 sm:px-6 sm:py-14">
        <div className="mx-auto max-w-[1240px]">
          {/* AI understands your tender */}
          <div className="grid items-center gap-8 lg:grid-cols-2 lg:gap-12">
            <div>
              <span className="mb-2 block text-[11px] font-semibold uppercase tracking-widest text-[#C8A96B]">
                AI Intelligence
              </span>
              <h2 className="mb-4 max-w-[520px] text-[28px] font-bold leading-snug tracking-tight text-[#162A4C]">
                AI that understands your tender — and your company.
              </h2>
              <p className="mb-6 max-w-[520px] text-[13px] leading-relaxed text-[#4b5f86]">
                TenderMind doesn’t just summarize documents. It compares every
                RFP against your capabilities, past projects, certifications,
                financial policies, risk policies, capacity and tender strategy.
              </p>

              <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {capabilities.map((item) => (
                  <li
                    key={item}
                    className="flex items-center gap-2 rounded-lg border border-[#ebe8e1] bg-white px-3.5 py-2.5 text-[13px] font-medium text-[#162A4C]"
                  >
                    <CheckCircle2
                      size={16}
                      strokeWidth={1.8}
                      className="shrink-0 text-[#4b5f86]"
                    />
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-2xl border border-[#ebe8e1] bg-white p-5 shadow-sm sm:p-6">
              <span className="mb-2 block text-[11px] font-semibold uppercase tracking-wider text-[#4b5f86]">
                RFP Requirement
              </span>
              <blockquote className="mb-5 border-l-2 border-[#C8A96B] pl-3 text-[16px] font-semibold leading-snug text-[#162A4C]">
                “Minimum 5 years experience in similar projects.”
              </blockquote>

              <div className="rounded-xl bg-[#e8ecf3] p-4">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <strong className="text-[11px] font-bold uppercase tracking-wide text-[#162A4C]">
                    TenderMind
                  </strong>
                  <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-600">
                    <Check size={12} strokeWidth={2.5} />
                    Requirement satisfied
                  </span>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {[
                    { name: "Project Alpha", meta: "8 years · SAR 12M" },
                    { name: "Project Beta", meta: "8 years · SAR 8M" },
                  ].map((p) => (
                    <div
                      key={p.name}
                      className="rounded-lg bg-white px-3.5 py-3 shadow-sm"
                    >
                      <p className="text-[13px] font-bold text-[#162A4C]">
                        {p.name}
                      </p>
                      <p className="mt-0.5 text-[12px] text-[#4b5f86]">
                        {p.meta}
                      </p>
                    </div>
                  ))}
                </div>

                <p className="mt-3 flex items-center gap-1.5 text-[12px] text-[#4b5f86]">
                  <FileText size={12} strokeWidth={1.8} />
                  Evidence: RFP Page 31 · Section 4.2
                </p>
              </div>
            </div>
          </div>

          {/* Go / No-Go */}
          <h2 className="mx-auto mb-8 mt-14 max-w-[640px] text-center text-[28px] font-bold leading-snug tracking-tight text-[#162A4C] sm:mt-20">
            Know when to bid before you spend days preparing.
          </h2>

          <div className="grid gap-8 rounded-[20px] bg-[#162A4C] p-6 sm:p-8 lg:grid-cols-[320px_1fr] lg:gap-10">
            <div className="flex flex-col">
              <span className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-[#C8A96B]">
                AI Recommendation
              </span>
              <h3 className="text-[22px] font-extrabold uppercase tracking-tight text-white">
                Conditional Go
              </h3>
              <p className="my-1 text-[48px] font-extrabold leading-none text-white">
                82 / 100
              </p>
              <p className="mb-6 mt-2 max-w-[240px] text-[13px] leading-snug text-[#a9b8d4]">
                Human approval required before proceeding.
              </p>

              <button
                type="button"
                className="w-full rounded-lg bg-[#C8A96B] px-4 py-3 text-[13px] font-bold text-[#162A4C] transition hover:brightness-110"
              >
                See How Go / No-Go Works
              </button>

              <p className="mt-3 flex items-center gap-1.5 text-[12px] text-[#a9b8d4]">
                <Lock size={12} strokeWidth={1.8} />
                Every decision needs a human owner
              </p>
            </div>

            <div>
              <ul className="space-y-4">
                {scores.map(({ label, value }) => (
                  <li key={label}>
                    <div className="mb-1.5 flex items-center justify-between text-[13px]">
                      <span className="font-semibold text-[#dbe4f5]">
                        {label}
                      </span>
                      <span className="font-bold text-white">{value}%</span>
                    </div>
                    <div
                      role="progressbar"
                      aria-valuenow={value}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={label}
                      className="h-[6px] w-full rounded-full bg-white/10"
                    >
                      <div
                        className="h-full rounded-full bg-[#C8A96B]"
                        style={{ width: `${value}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ul>

              <div className="mt-6 rounded-xl border border-white/10 bg-white/5 p-4">
                <span className="mb-3 block text-[11px] font-semibold uppercase tracking-widest text-[#C8A96B]">
                  Why?
                </span>
                <ul className="grid grid-cols-1 gap-x-6 gap-y-2.5 sm:grid-cols-2">
                  {reasons.map(({ ok, text }) => (
                    <li
                      key={text}
                      className="flex items-center gap-2 text-[13px] text-[#dbe4f5]"
                    >
                      {ok ? (
                        <Check size={14} strokeWidth={2.5} className="shrink-0 text-white" />
                      ) : (
                        <AlertTriangle size={14} strokeWidth={2} className="shrink-0 text-[#C8A96B]" />
                      )}
                      {text}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Financial Intelligence */}
      <section className="bg-[#0F1D38] px-4 py-12 sm:px-6 sm:py-16">
        <div className="mx-auto grid max-w-[1240px] items-center gap-10 lg:grid-cols-2">
          <div>
            <span className="mb-2 block text-[11px] font-semibold uppercase tracking-widest text-[#C8A96B]">
              Financial Intelligence
            </span>
            <h2 className="mb-3 max-w-[560px] text-[28px] font-bold leading-snug tracking-tight text-white">
              Don’t evaluate a tender without understanding its financial impact.
            </h2>
            <p className="mb-6 text-[14px] text-[#a9b8d4]">
              Give Finance the information they need before the commercial decision.
            </p>

            <div className="mb-4 grid grid-cols-2 gap-3">
              {finStats.map(({ label, value }) => (
                <div key={label} className="rounded-xl border border-white/15 px-4 py-4">
                  <p className="text-[12px] text-[#a9b8d4]">{label}</p>
                  <p className="mt-1 text-[24px] font-bold text-white">{value}</p>
                </div>
              ))}
            </div>

            <p className="inline-flex items-center gap-2 rounded-md bg-[#fadfdf] px-3.5 py-2 text-[12px] font-semibold text-[#c0453f]">
              <AlertTriangle size={14} strokeWidth={2} className="shrink-0" />
              Cash Flow Risk: HIGH — 90-day terms + 10% retention strain Q2–Q3.
            </p>
          </div>

          <div className="rounded-2xl bg-white p-5 sm:p-6">
            <div className="mb-6 flex items-center justify-between">
              <h3 className="text-[14px] font-bold text-[#162A4C]">Projected cash exposure</h3>
              <span className="text-[12px] text-[#4b5f86]">12 months · SAR</span>
            </div>
            <div className="flex h-[170px] items-end gap-2">
              {cashBars.map((h, i) => (
                <div
                  key={i}
                  className={`flex-1 rounded-t-md ${barColor(i)}`}
                  style={{ height: `${h}%` }}
                />
              ))}
            </div>
            <div className="mt-2 flex justify-between text-[11px] text-[#4b5f86]">
              <span>M1</span>
              <span>M6</span>
              <span>M12</span>
            </div>
            <ul className="mt-4 flex flex-wrap gap-4 text-[12px] text-[#4b5f86]">
              {[
                ["Outflow", "bg-[#162A4C]"],
                ["Peak strain", "bg-[#D06A68]"],
                ["Recovery", "bg-[#C8A96B]"],
              ].map(([name, dot]) => (
                <li key={name} className="flex items-center gap-1.5">
                  <span className={`h-2 w-2 rounded-full ${dot}`} />
                  {name}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* Workflow cards + Security + Features */}
      <section className="space-y-14 bg-[#f5f3ee] px-4 py-10 sm:space-y-20 sm:px-6 sm:py-14">
        <div className="mx-auto grid max-w-[1240px] gap-4 lg:grid-cols-3">
          {/* Team workflow */}
          <article className="rounded-2xl border border-[#ebe8e1] bg-white p-6">
            <Network size={18} strokeWidth={1.8} className="mb-4 text-[#162A4C]" />
            <h3 className="mb-4 text-[18px] font-bold leading-snug text-[#162A4C]">
              Turn one RFP into an organized team workflow.
            </h3>
            <ul className="space-y-2">
              {disciplines.map((d) => (
                <li
                  key={d}
                  className="flex items-center justify-between gap-2 rounded-lg border border-[#ebe8e1] bg-[#f5f3ee] px-3.5 py-2.5"
                >
                  <span className="text-[13px] font-semibold text-[#162A4C]">{d}</span>
                  <span className="truncate text-[11px] text-[#4b5f86]">Tasks · Owner · Deadline</span>
                </li>
              ))}
            </ul>
          </article>

          {/* Decision makers */}
          <article className="rounded-2xl border border-[#ebe8e1] bg-white p-6">
            <Stamp size={18} strokeWidth={1.8} className="mb-4 text-[#162A4C]" />
            <h3 className="mb-5 text-[18px] font-bold leading-snug text-[#162A4C]">
              Bring every decision maker into one workflow.
            </h3>
            <ul className="space-y-3.5">
              {approvals.map(({ name, status, done, n }) => (
                <li key={name} className="flex items-center gap-3">
                  <span
                    className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[12px] font-bold ${
                      done ? "bg-emerald-100 text-emerald-600" : "bg-[#f3ead6] text-[#C8A96B]"
                    }`}
                  >
                    {done ? <Check size={14} strokeWidth={2.5} /> : n}
                  </span>
                  <span className="flex-1 text-[13px] font-semibold text-[#162A4C]">{name}</span>
                  {status && (
                    <span
                      className={`text-[12px] ${done ? "text-emerald-700" : "text-[#C8A96B]"}`}
                    >
                      {status}
                    </span>
                  )}
                </li>
              ))}
            </ul>
            <p className="mt-5 text-[12px] leading-relaxed text-[#4b5f86]">
              Every approval is documented. Every decision has an owner. Every action has a timestamp.
            </p>
          </article>

          {/* Subcontractor RFQs */}
          <article className="rounded-2xl border border-[#ebe8e1] bg-white p-6">
            <Truck size={18} strokeWidth={1.8} className="mb-4 text-[#162A4C]" />
            <h3 className="mb-4 text-[18px] font-bold leading-snug text-[#162A4C]">
              Turn RFP requirements into subcontractor RFQs.
            </h3>
            <div className="rounded-xl border border-[#ebe8e1] bg-[#f5f3ee] p-4">
              <p className="text-[13px] font-bold text-[#162A4C]">Mechanical Work Package</p>
              <p className="mb-3 text-[12px] text-[#4b5f86]">HVAC · SAR 2.1M estimate</p>
              <ol className="space-y-2">
                {rfqSteps.map((step, i) => (
                  <li key={step} className="flex items-center gap-2.5 text-[12px] text-[#4b5f86]">
                    <span
                      className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
                        i < 3 ? "bg-[#162A4C] text-white" : "bg-[#ebe8e1] text-[#4b5f86]"
                      }`}
                    >
                      {i + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="rounded-full bg-[#e8ecf3] px-3 py-1 text-[11px] font-semibold text-[#162A4C]">
                Bid Management
              </span>
              <span className="rounded-full bg-[#f3ead6] px-3 py-1 text-[11px] font-semibold text-[#a88645]">
                Subcontractor Procurement
              </span>
            </div>
          </article>
        </div>

        {/* Security */}
        <div className="mx-auto grid max-w-[1240px] gap-8 rounded-2xl border border-[#ebe8e1] bg-white p-6 sm:p-8 lg:grid-cols-2 lg:gap-12">
          <div>
            <h2 className="mb-4 text-[24px] font-bold leading-snug tracking-tight text-[#162A4C]">
              Your tenders contain sensitive information. We treat them that way.
            </h2>
            <ul className="mb-6 grid grid-cols-1 gap-x-6 gap-y-2.5 sm:grid-cols-2">
              {securityItems.map((item) => (
                <li key={item} className="flex items-center gap-2 text-[13px] text-[#162A4C]">
                  <Lock size={14} strokeWidth={1.8} className="shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="rounded-lg border-2 border-[#162A4C] px-4 py-2.5 text-[13px] font-semibold text-[#162A4C] transition hover:bg-[#162A4C] hover:text-white"
            >
              Explore Security
            </button>
          </div>

          <div className="space-y-3 self-center rounded-xl border border-[#ebe8e1] bg-[#f5f3ee] p-5 font-mono text-[12px] text-[#4b5f86]">
            {auditLog.map((line) => (
              <p key={line} className="break-words">{line}</p>
            ))}
            <p className="break-words text-emerald-700">
              [09:51:40] approved · signed · timestamped
            </p>
          </div>
        </div>

        {/* Features */}
        <div className="mx-auto max-w-[1240px]">
          <h2 className="mb-8 text-center text-[28px] font-bold tracking-tight text-[#162A4C]">
            Everything a tender team needs.
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {features.map(({ icon: Icon, title, text }) => (
              <article key={title} className="rounded-xl border border-[#ebe8e1] bg-white p-5">
                <span className="mb-4 inline-flex h-[34px] w-[34px] items-center justify-center rounded-lg bg-[#eef0f4] text-[#162A4C]">
                  <Icon size={16} strokeWidth={1.8} />
                </span>
                <h3 className="mb-1.5 text-[14px] font-bold text-[#162A4C]">{title}</h3>
                <p className="text-[13px] leading-relaxed text-[#4b5f86]">{text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-[#162A4C] px-4 py-16 text-center sm:px-6 sm:py-20">
        <span className="mb-3 block text-[11px] font-semibold uppercase tracking-widest text-[#C8A96B]">
          From RFP to ready-to-bid
        </span>
        <h2 className="mx-auto mb-8 max-w-[720px] text-[32px] font-bold leading-snug tracking-tight text-white">
          Understand the tender. Decide with confidence. Coordinate the team. Submit on time.
        </h2>
        <div className="flex flex-wrap justify-center gap-3">
          <button
            type="button"
            className="rounded-lg bg-[#C8A96B] px-6 py-3 text-[13px] font-bold text-[#162A4C] transition hover:brightness-110"
          >
            Book a Demo
          </button>
          <button
            type="button"
            className="rounded-lg border border-white/30 px-6 py-3 text-[13px] font-semibold text-white transition hover:bg-white/10"
          >
            See How It Works
          </button>
        </div>
      </section>

      {/* Footer */}
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
      </footer>

      {/* Back to top */}
      <button
        type="button"
        aria-label="Back to top"
        onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        className={`fixed bottom-6 right-6 z-50 flex items-center gap-1.5 rounded-full bg-[#C8A96B] px-4 py-3 text-[12px] font-bold tracking-wide text-[#162A4C] shadow-lg transition-all duration-300 hover:brightness-110 ${
          showTop
            ? "translate-y-0 opacity-100"
            : "pointer-events-none translate-y-4 opacity-0"
        }`}
      >
        <ArrowUp size={14} strokeWidth={2.5} />
        TOP
      </button>
    </>
  );
}

export default Home;
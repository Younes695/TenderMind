import { CheckCircle2, AlertTriangle, FileText, Lock } from "lucide-react";

const scores = [
  { label: "Technical Fit", value: 92 },
  { label: "Financial Fit", value: 68 },
  { label: "Risk", value: 74 },
  { label: "Evaluation Fit", value: 88 },
  { label: "Capacity", value: 80 },
];

const reasoning = [
  {
    type: "ok",
    icon: CheckCircle2,
    title: "Strong technical experience in smart infrastructure",
    evidence: "RFP Page 31 · Section 4.2",
  },
  {
    type: "ok",
    icon: CheckCircle2,
    title: "Required certifications available (ISO 9001, Saudization)",
    evidence: "Knowledge Base · verified",
  },
  {
    type: "warn",
    icon: AlertTriangle,
    title: "Payment terms exceed company policy (90 vs 60 days)",
    evidence: "RFP Page 47 · Section 8.2",
  },
  {
    type: "warn",
    icon: AlertTriangle,
    title: "High performance guarantee (10% vs 5% policy cap)",
    evidence: "RFP Page 52 · Section 9.1",
  },
];

function ScoreBar({ label, value }) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <span className="text-[15px] text-[#c5d0e6]">{label}</span>
        <span className="text-[16px] font-bold text-white">{value}%</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/15">
        <div
          className="h-full rounded-full bg-[#C8A96B]"
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

function GoNoGo() {
  return (
    <div className="min-h-screen bg-[#f8f7f3] p-4 sm:p-6 lg:p-8">
      <div className="mx-auto grid max-w-[1450px] grid-cols-1 gap-4 lg:grid-cols-[400px_minmax(0,1fr)] lg:gap-5">
        {/* ============ Left: AI Recommendation ============ */}
        <section className="rounded-[20px] bg-[#101E38] p-6 sm:p-8">
          <p className="text-[13px] font-bold tracking-[0.18em] text-[#C8A96B]">
            AI RECOMMENDATION
          </p>

          <h2 className="mt-2 text-[30px] font-black leading-tight text-white sm:text-[34px]">
            CONDITIONAL GO
          </h2>

          <p className="mt-2 flex items-end gap-1">
            <span className="text-[60px] font-black leading-none text-white sm:text-[68px]">
              82
            </span>
            <span className="pb-1 text-[20px] font-bold text-white/40">
              /100
            </span>
          </p>

          <div className="mt-6 space-y-5">
            {scores.map((s) => (
              <ScoreBar key={s.label} label={s.label} value={s.value} />
            ))}
          </div>

          <div className="mt-7 flex items-start gap-2.5 rounded-xl bg-white/10 p-4">
            <Lock size={18} className="mt-0.5 shrink-0 text-white" />
            <p className="text-[14px] leading-relaxed text-white">
              AI recommends — humans decide. Finance approval required.
            </p>
          </div>
        </section>

        {/* ============ Right: AI Reasoning ============ */}
        <section className="rounded-[20px] border border-[#e5e1d9] bg-white p-6 sm:p-8">
          <h2 className="text-[20px] font-bold text-[#162A4C] sm:text-[22px]">
            AI reasoning — every claim carries evidence
          </h2>

          <div className="mt-5 space-y-4">
            {reasoning.map(({ type, icon: Icon, title, evidence }) => (
              <div
                key={title}
                className={`flex items-start gap-3 rounded-2xl border p-5 ${
                  type === "warn"
                    ? "border-[#e6d3a3] bg-[#fdf4de]"
                    : "border-[#e8e4dc] bg-[#faf9f6]"
                }`}
              >
                <Icon
                  size={22}
                  strokeWidth={2}
                  className="mt-0.5 shrink-0 text-[#162A4C]"
                />
                <div className="min-w-0">
                  <p className="text-[15px] font-bold leading-snug text-[#162A4C] sm:text-[16px]">
                    {title}
                  </p>
                  <p className="mt-1.5 flex items-center gap-1.5 text-[14px] text-[#647494]">
                    <FileText size={15} className="shrink-0" />
                    <span>
                      Evidence: <span className="font-medium">{evidence}</span>
                    </span>
                  </p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <button
              type="button"
              className="h-[52px] rounded-xl bg-[#2E7D5B] px-7 text-[16px] font-bold text-white transition-colors hover:bg-[#256845]"
            >
              Approve Go
            </button>
            <button
              type="button"
              className="h-[52px] rounded-xl bg-[#C84A4A] px-7 text-[16px] font-bold text-white transition-colors hover:bg-[#ad3d3d]"
            >
              Reject (No-Go)
            </button>
            <button
              type="button"
              className="h-[52px] rounded-xl border border-[#e2e6ee] bg-white px-7 text-[16px] font-bold text-[#162A4C] transition-colors hover:bg-[#f5f6f9]"
            >
              Request changes
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}

export default GoNoGo;

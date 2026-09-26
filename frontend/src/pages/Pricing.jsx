import { Check } from "lucide-react";

const plans = [
  {
    name: "Starter",
    tagline: "For smaller teams",
    price: "Talk to Sales",
    features: [
      "Tender Intelligence",
      "RFP Summaries",
      "Basic Matching",
      "Document Analysis",
    ],
    cta: "Start Trial",
    highlighted: false,
  },
  {
    name: "Professional",
    tagline: "For growing tender teams",
    price: "Talk to Sales",
    badge: "Most Popular",
    features: [
      "Everything in Starter",
      "Go / No-Go",
      "Financial Analysis",
      "Risk Analysis",
      "Team Workflow",
      "Approvals",
      "Company Knowledge",
    ],
    cta: "Book a Demo",
    highlighted: true,
  },
  {
    name: "Enterprise",
    tagline: "For large organizations",
    price: "Custom",
    features: [
      "Everything in Professional",
      "Advanced Workflows",
      "Subcontractor RFQs",
      "Advanced Security",
      "Custom Integrations",
      "Multiple Teams",
      "Advanced Analytics",
    ],
    cta: "Talk to Sales",
    highlighted: false,
  },
];

function Pricing() {
  return (
    <section className="bg-[#f5f3ee] py-14 sm:py-16">
      <div className="mx-auto max-w-[1190px] px-4 sm:px-6 lg:px-8">
        {/* Heading */}
        <div className="mb-10 text-center">
          <span className="mb-3 block text-[11px] font-semibold uppercase tracking-widest text-[#C8A96B]">
            Pricing
          </span>
          <h1 className="text-[32px] font-bold leading-tight tracking-tight text-[#162A4C] sm:text-[38px]">
            Priced for how tender teams grow.
          </h1>
        </div>

        {/* Plans */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {plans.map(({ name, tagline, price, features, cta, highlighted, badge }) => (
            <article
              key={name}
              className={`relative flex flex-col rounded-2xl border p-6 sm:p-7 ${
                highlighted
                  ? "border-[#C8A96B] bg-[#162A4C] lg:-my-4 lg:py-10"
                  : "border-[#ebe8e1] bg-white"
              }`}
            >
              {badge && (
                <span className="mb-4 inline-flex w-fit items-center rounded-full bg-[#C8A96B] px-3 py-1 text-[10px] font-bold uppercase tracking-wide text-[#162A4C]">
                  {badge}
                </span>
              )}

              <h2
                className={`text-[18px] font-bold ${
                  highlighted ? "text-white" : "text-[#162A4C]"
                }`}
              >
                {name}
              </h2>
              <p
                className={`mt-1 text-[13px] ${
                  highlighted ? "text-[#a9b8d4]" : "text-[#4b5f86]"
                }`}
              >
                {tagline}
              </p>

              <p
                className={`mb-6 mt-5 text-[22px] font-bold ${
                  highlighted ? "text-white" : "text-[#162A4C]"
                }`}
              >
                {price}
              </p>

              <ul className="mb-8 flex-1 space-y-3">
                {features.map((f) => (
                  <li
                    key={f}
                    className={`flex items-start gap-2 text-[13px] ${
                      highlighted ? "text-[#dbe4f5]" : "text-[#4b5f86]"
                    }`}
                  >
                    <Check
                      size={15}
                      strokeWidth={2.4}
                      className={`mt-0.5 shrink-0 ${
                        highlighted ? "text-[#C8A96B]" : "text-emerald-600"
                      }`}
                    />
                    {f}
                  </li>
                ))}
              </ul>

              <button
                type="button"
                className={`w-full rounded-lg px-4 py-3 text-[13px] font-bold transition-colors ${
                  highlighted
                    ? "bg-[#C8A96B] text-[#162A4C] hover:brightness-110"
                    : "bg-[#162A4C] text-white hover:bg-[#0F1D38]"
                }`}
              >
                {cta}
              </button>
            </article>
          ))}
        </div>

        {/* Footnote */}
        <p className="mt-10 text-center text-[13px] text-[#4b5f86]">
          Annual tenders volume and average tender value shape every quote.
          Pricing in SAR / AED available from sales.
        </p>
      </div>
    </section>
  );
}

export default Pricing;
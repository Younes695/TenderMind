import { Check } from "lucide-react";
import { useT } from "../i18n";

// Initial pricing hypothesis (same as the financial model) — being validated with pilot customers.
const plans = [
  {
    name: "Starter",
    tagline: "Individual / small business",
    price: "EGP 1,500",
    gcc: "SAR 299",
    per: "/ month",
    features: [
      "5 tender analyses / month",
      "Tender Radar with match % and reasons",
      "AI RFP analysis — every fact with file and page",
      "Eligibility check against your profile",
      "Ask TenderMind",
    ],
    cta: "Start Trial",
    highlighted: false,
  },
  {
    name: "Growth",
    tagline: "Tender team / growing company",
    price: "EGP 4,900",
    gcc: "SAR 899",
    per: "/ month",
    badge: "Most Popular",
    features: [
      "15 tender analyses / month",
      "Everything in Starter",
      "Team tasks, votes and approvals",
      "BOQ materials with your supplier price lists",
      "RFQ packages per equipment",
    ],
    cta: "Book a Demo",
    highlighted: true,
  },
  {
    name: "Business",
    tagline: "Larger company / multiple users",
    price: "EGP 14,900",
    gcc: "SAR 2,900",
    per: "/ month",
    features: [
      "60 tender analyses / month",
      "Everything in Growth",
      "Same materials across all active tenders",
      "Decision pack, compliance matrix and analytics",
      "Multiple teams",
    ],
    cta: "Book a Demo",
    highlighted: false,
  },
  {
    name: "Enterprise",
    tagline: "Dedicated cloud / private deployment",
    price: "From EGP 45,000",
    gcc: "From SAR 9,500",
    per: "/ month",
    features: [
      "Dedicated cloud hosted by us",
      "On-premise option (quoted separately)",
      "Your own AI keys and data residency",
      "Custom tender sources and integrations",
      "Priority support",
    ],
    cta: "Talk to Sales",
    highlighted: false,
  },
];

function Pricing() {
  const t = useT();
  return (
    <section className="bg-[#f5f3ee] py-14 sm:py-16">
      <div className="mx-auto max-w-[1190px] px-4 sm:px-6 lg:px-8">
        {/* Heading */}
        <div className="mb-10 text-center">
          <span className="mb-3 block text-[11px] font-semibold uppercase tracking-widest text-[#C8A96B]">
            {t("Pricing")}
          </span>
          <h1 className="text-[32px] font-bold leading-tight tracking-tight text-[#162A4C] sm:text-[38px]">
            {t("Priced for how tender teams grow.")}
          </h1>
        </div>

        {/* Plans */}
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4">
          {plans.map(({ name, tagline, price, gcc, per, features, cta, highlighted, badge }) => (
            <article
              key={name}
              className={`relative flex flex-col rounded-2xl border p-6 sm:p-7 ${
                highlighted
                  ? "border-[#C8A96B] bg-[#162A4C] xl:-my-4 xl:py-10"
                  : "border-[#ebe8e1] bg-white"
              }`}
            >
              {badge && (
                <span className="mb-4 inline-flex w-fit items-center rounded-full bg-[#C8A96B] px-3 py-1 text-[10px] font-bold uppercase tracking-wide text-[#162A4C]">
                  {t(badge)}
                </span>
              )}

              <h2
                className={`text-[18px] font-bold ${
                  highlighted ? "text-white" : "text-[#162A4C]"
                }`}
              >
                {t(name)}
              </h2>
              <p
                className={`mt-1 text-[13px] ${
                  highlighted ? "text-[#a9b8d4]" : "text-[#4b5f86]"
                }`}
              >
                {t(tagline)}
              </p>

              <p
                className={`mb-6 mt-5 text-[22px] font-bold ${
                  highlighted ? "text-white" : "text-[#162A4C]"
                }`}
              >
                {t(price)}
                {per && <span className={`ms-1 text-[13px] font-medium ${highlighted ? "text-[#a9b8d4]" : "text-[#4b5f86]"}`}>{t(per)}</span>}
              </p>
              {gcc && <p className={`-mt-5 mb-6 text-[12px] ${highlighted ? "text-[#a9b8d4]" : "text-[#4b5f86]"}`}>{t("GCC: {p} / month", { p: t(gcc) })}</p>}

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
                    {t(f)}
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
                {t(cta)}
              </button>
            </article>
          ))}
        </div>

        {/* Footnote */}
        <p className="mt-10 text-center text-[13px] text-[#4b5f86]">
          {t("Prices exclude VAT. Egypt prices in EGP, GCC prices in SAR.")}
        </p>
      </div>
    </section>
  );
}

export default Pricing;
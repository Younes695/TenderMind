import { Link } from "react-router-dom";
import {
  Building2,
  Waypoints,
  Camera,
  ShieldCheck,
  Network,
  Wrench,
  Zap,
  Landmark,
  ChevronRight,
} from "lucide-react";

const industries = [
  {
    icon: Building2,
    title: "Construction",
    text: "BOQs, bonds and retention modelled per package.",
  },
  {
    icon: Waypoints,
    title: "Engineering",
    text: "Multi-discipline decomposition with design-review gates.",
  },
  {
    icon: Camera,
    title: "IT & Technology",
    text: "Scope, SLA and licensing obligations extracted automatically.",
  },
  {
    icon: ShieldCheck,
    title: "Cybersecurity",
    text: "Compliance-mapped requirements with evidence chains.",
  },
  {
    icon: Network,
    title: "Infrastructure",
    text: "Long-duration cash exposure across milestones.",
  },
  {
    icon: Wrench,
    title: "Facility Management",
    text: "Recurring-service terms and KPI penalties flagged.",
  },
  {
    icon: Zap,
    title: "Energy",
    text: "Local-content and certification matching for GCC bids.",
  },
  {
    icon: Landmark,
    title: "Government Contractors",
    text: "Etimad-aligned intake with audit-ready approvals.",
  },
];

function Industries() {
  return (
    <>
      {/* Hero band */}
      <section className="bg-[#162A4C] py-14 sm:py-16">
        <div className="mx-auto max-w-[1190px] px-4 sm:px-6 lg:px-8">
          <h1 className="mb-4 max-w-[640px] text-[32px] font-bold leading-tight tracking-tight text-white sm:text-[38px]">
            We understand complex tenders in your sector.
          </h1>
          <p className="max-w-[560px] text-[14px] leading-relaxed text-[#c5d0e6]">
            Pre-tuned requirement libraries and risk policies for Saudi
            Arabia, the UAE, Egypt and the GCC.
          </p>
        </div>
      </section>

      {/* Industry cards */}
      <section className="bg-[#f5f3ee] py-10 sm:py-14">
        <div className="mx-auto grid max-w-[1190px] grid-cols-1 gap-4 px-4 sm:grid-cols-2 sm:px-6 lg:grid-cols-4 lg:px-8">
          {industries.map(({ icon: Icon, title, text }) => (
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
              <p className="mb-4 text-[13px] leading-relaxed text-[#4b5f86]">
                {text}
              </p>
              <Link
                to={`/industries/${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
                className="inline-flex items-center gap-1 text-[13px] font-bold text-[#162A4C] transition-colors hover:text-[#C8A96B]"
              >
                Explore
                <ChevronRight size={14} strokeWidth={2.2} />
              </Link>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

export default Industries;
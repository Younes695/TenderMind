import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";
import apiClient from "../api/client";
import { useT } from "../i18n";

const COUNTRIES = ["Egypt", "Saudi Arabia", "United Arab Emirates", "Qatar", "Kuwait", "Bahrain", "Oman"];
const TOPIC_LABEL = {
  "plan:starter": "Starter plan", "plan:growth": "Growth plan", "plan:business": "Business plan",
  "plan:enterprise": "Enterprise (dedicated cloud / on-premise)", security: "Security review", demo: "Product demo",
};

/** Public "Book a demo / Talk to sales" form. The request is stored for the team — nothing is emailed. */
export default function Demo() {
  const t = useT();
  const [params] = useSearchParams();
  const topic = params.get("topic") || "demo";
  const [form, setForm] = useState({ name: "", email: "", company: "", country: "Egypt", message: "", website: "" });
  const [state, setState] = useState({ busy: false, done: false, error: "" });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    setState({ busy: true, done: false, error: "" });
    try {
      await apiClient.requestDemo({ ...form, topic });
      setState({ busy: false, done: true, error: "" });
    } catch (err) {
      setState({ busy: false, done: false, error: t(err.message || "Could not send") });
    }
  };
  const input = "mt-1 w-full rounded-lg border border-[#d9d4c9] bg-white px-3 py-2.5 text-[14px] text-[#162A4C] outline-none focus:border-[#162A4C]";
  return (
    <section className="bg-[#f5f3ee] px-4 py-14 sm:py-16">
      <div className="mx-auto grid max-w-[1000px] gap-10 lg:grid-cols-[1fr_1.1fr]">
        <div>
          <h1 className="text-[32px] font-bold leading-tight text-[#162A4C]">{t("See TenderMind on one of your own tenders")}</h1>
          <p className="mt-3 text-[15px] leading-relaxed text-[#4b5f86]">
            {t("Send us a tender you are working on. We walk your team through the analysis: requirements with their pages, eligibility, BOQ materials, RFQ packages and the decision pack.")}
          </p>
          <ul className="mt-6 space-y-2 text-[14px] text-[#344054]">
            {["30-minute online session", "Arabic or English", "Egypt and GCC tenders"].map((x) => (
              <li key={x} className="flex items-center gap-2"><CheckCircle2 size={16} className="text-[#C8A96B]" /> {t(x)}</li>
            ))}
          </ul>
          <p className="mt-6 text-[13px] text-[#4b5f86]">{t("Prefer to try it yourself?")} <Link to="/signup" className="font-semibold text-[#162A4C] underline">{t("Create an account")}</Link></p>
        </div>
        <div className="rounded-2xl border border-[#ebe8e1] bg-white p-6 sm:p-7">
          {state.done ? (
            <div data-testid="demo-done" className="py-10 text-center">
              <CheckCircle2 size={40} className="mx-auto text-[#1f7a4d]" />
              <p className="mt-3 text-[18px] font-bold text-[#162A4C]">{t("Thank you — we received your request")}</p>
              <p className="mt-1 text-[14px] text-[#4b5f86]">{t("We will contact you by email to schedule the session.")}</p>
              <Link to="/" className="mt-5 inline-block text-[14px] font-semibold text-[#162A4C] underline">{t("Back to the home page")}</Link>
            </div>
          ) : (
            <form onSubmit={submit} data-testid="demo-form" className="space-y-3">
              <p className="rounded-lg bg-[#f5f3ee] px-3 py-2 text-[13px] text-[#4b5f86]">{t("Request")}: <b className="text-[#162A4C]">{t(TOPIC_LABEL[topic] || "Product demo")}</b></p>
              <label className="block text-[13px] font-semibold text-[#162A4C]">{t("Full name")}
                <input required className={input} value={form.name} onChange={set("name")} maxLength={120} /></label>
              <label className="block text-[13px] font-semibold text-[#162A4C]">{t("Work Email")}
                <input required type="email" className={input} value={form.email} onChange={set("email")} /></label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-[13px] font-semibold text-[#162A4C]">{t("Company")}
                  <input className={input} value={form.company} onChange={set("company")} maxLength={200} /></label>
                <label className="block text-[13px] font-semibold text-[#162A4C]">{t("Country")}
                  <select className={input} value={form.country} onChange={set("country")}>
                    {COUNTRIES.map((c) => <option key={c} value={c}>{t(c)}</option>)}
                  </select></label>
              </div>
              <label className="block text-[13px] font-semibold text-[#162A4C]">{t("What would you like to see?")}
                <textarea className={input} rows={3} value={form.message} onChange={set("message")} maxLength={2000} /></label>
              <input type="text" name="website" value={form.website} onChange={set("website")} tabIndex={-1} autoComplete="off"
                aria-hidden="true" className="hidden" />
              {state.error && <p className="text-[13px] text-[#b42318]">{state.error}</p>}
              <button type="submit" disabled={state.busy} className="w-full rounded-lg bg-[#162A4C] px-4 py-3 text-[14px] font-bold text-white disabled:opacity-50">
                {state.busy ? t("Sending…") : t("Request a demo")}
              </button>
            </form>
          )}
        </div>
      </div>
    </section>
  );
}

import { useState } from "react";
import { Lock, Globe, ChevronDown, ShieldCheck, FileSearch, Cloud } from "lucide-react";
import bgLogin from "../assets/bg_home.jpg";
import logo from "../assets/logo.jpg";

const features = [
  { icon: ShieldCheck, title: "Role-based access", text: "Secure access for every team member." },
  { icon: FileSearch, title: "Evidence on every claim", text: "Every insight is backed by source documents." },
  { icon: Cloud, title: "KSA data residency", text: "Your data is stored and processed in Saudi Arabia." },
];

export function Logo({ dark = false }) {
  return (
    <div className="flex items-center gap-3">
      <img src={logo} alt="TenderMind logo" className="h-10 w-10 rounded-md object-cover" />
      <span className="text-[24px] font-black tracking-wide">
        <span className={dark ? "text-[#162A4C]" : "text-white"}>TENDER</span>
        <span className="text-[#C8A96B]">MIND</span>
      </span>
    </div>
  );
}

/** Shared frame for the log-in and sign-up pages (brand panel + form column). */
export default function AuthLayout({ heading, intro, children }) {
  const [lang, setLang] = useState("en");
  return (
    <main className="grid min-h-screen bg-[#fafafa] lg:grid-cols-[44%_56%]">
      <aside
        className="relative hidden flex-col justify-between bg-[#162A4C] bg-cover bg-center text-white lg:flex"
        style={{ backgroundImage: `linear-gradient(rgba(15,29,56,0.9), rgba(15,29,56,0.94)), url(${bgLogin})` }}
      >
        <div className="bg-[#0F1D38]/60 px-10 py-6">
          <Logo />
        </div>
        <div className="px-10 py-10">
          <h1 className="mb-4 text-[40px] font-bold leading-tight tracking-tight">{heading}</h1>
          <p className="mb-10 max-w-[380px] text-[16px] leading-8 text-[#dbe4f5]">{intro}</p>
          <ul className="mb-10 space-y-7">
            {features.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex items-center gap-5">
                <span className="flex h-[70px] w-[70px] shrink-0 items-center justify-center rounded-full bg-white/10 text-[#C8A96B]">
                  <Icon size={30} strokeWidth={1.6} />
                </span>
                <div className="max-w-[240px]">
                  <p className="text-[14px] font-bold">{title}</p>
                  <p className="mt-0.5 text-[13px] leading-relaxed text-[#c5d0e6]">{text}</p>
                </div>
              </li>
            ))}
          </ul>
          <div className="flex max-w-[420px] items-start gap-4 rounded-xl border border-white/15 bg-white/5 p-5">
            <Lock size={20} strokeWidth={1.8} className="mt-0.5 shrink-0" />
            <div>
              <p className="text-[14px] font-bold">Your security is our priority</p>
              <p className="mt-0.5 text-[13px] leading-relaxed text-[#c5d0e6]">We use enterprise-grade security to protect your data.</p>
            </div>
          </div>
        </div>
        <footer className="px-10 pb-10 text-[13px] text-[#c5d0e6]">
          <p className="mb-2">© {new Date().getFullYear()} TenderMind. All rights reserved.</p>
          <nav className="flex items-center gap-3">
            <a href="/privacy" className="hover:text-white">Privacy Policy</a>
            <span className="text-white/30">|</span>
            <a href="/terms" className="hover:text-white">Terms of Service</a>
            <span className="text-white/30">|</span>
            <a href="/security" className="hover:text-white">Security</a>
          </nav>
        </footer>
      </aside>

      <section className="relative flex flex-col px-4 py-6 sm:px-8">
        <div className="flex items-center justify-between">
          <div className="lg:invisible">
            <Logo dark />
          </div>
          <label className="relative flex items-center rounded-lg border border-[#e2e6ee] bg-white text-[13px] text-[#162A4C]">
            <Globe size={16} strokeWidth={1.8} className="pointer-events-none absolute left-3" />
            <select value={lang} onChange={(e) => setLang(e.target.value)} aria-label="Language"
              className="h-10 appearance-none bg-transparent pl-9 pr-9 font-medium outline-none">
              <option value="en">English</option>
              <option value="ar">العربية</option>
            </select>
            <ChevronDown size={14} className="pointer-events-none absolute right-3" />
          </label>
        </div>
        <div className="flex flex-1 items-center justify-center py-8">
          <div className="w-full max-w-[540px] rounded-2xl border border-[#ebe8e1] bg-white p-7 shadow-sm sm:p-10">
            {children}
          </div>
        </div>
      </section>
    </main>
  );
}

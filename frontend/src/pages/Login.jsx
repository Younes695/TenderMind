import { useState } from "react";
import {
  Mail,
  Lock,
  Eye,
  EyeOff,
  Globe,
  ChevronDown,
  ShieldCheck,
  FileSearch,
  Cloud,
} from "lucide-react";
import bgLogin from "../assets/bg_home.jpg";
import logo from "../assets/logo.jpg";
import { GoogleLogin } from "@react-oauth/google";
import { useNavigate } from "react-router-dom";
const features = [
  {
    icon: ShieldCheck,
    title: "Role-based access",
    text: "Secure access for every team member.",
  },
  {
    icon: FileSearch,
    title: "Evidence on every claim",
    text: "Every insight is backed by source documents.",
  },
  {
    icon: Cloud,
    title: "KSA data residency",
    text: "Your data is stored and processed in Saudi Arabia.",
  },
];

function Logo({ dark = false }) {
  return (
    <div className="flex items-center gap-3">
      <img
        src={logo}
        alt="TenderMind logo"
        className="h-10 w-10 rounded-md object-cover"
      />
      <span className="text-[24px] font-black font-bold tracking-wide">
        <span className={dark ? "text-[#162A4C]" : "text-white"}>TENDER</span>
        <span className="text-[#C8A96B]">MIND</span>
      </span>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4.1 7.1-10.1 7.1-17.5z" />
      <path fill="#FBBC05" d="M10.5 28.7c-.5-1.4-.8-3-.8-4.7s.3-3.2.8-4.7l-7.9-6.1C.9 16.4 0 20.100 0 24s.9 7.600 2.600 10.800l7.900-6.100z" />
      <path fill="#34A853" d="M24 48c6.500 0 11.900-2.100 15.900-5.800l-7.500-5.800c-2.100 1.400-4.800 2.300-8.400 2.300-6.300 0-11.600-4.100-13.500-9.800l-7.900 6.100C6.500 42.600 14.600 48 24 48z" />
    </svg>
  );
}

function MicrosoftIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 21 21" aria-hidden="true">
      <rect x="1" y="1" width="9" height="9" fill="#F25022" />
      <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
      <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
      <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
    </svg>
  );
}

function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [lang, setLang] = useState("en");

  const handleSubmit = (e) => {
    e.preventDefault();
    // TODO: اربطي هنا بالـ API بتاع تسجيل الدخول
    console.log({ email, password, remember });
  };

  const inputClass =
    "h-[54px] w-full rounded-lg border border-[#e2e6ee] bg-white pl-11 text-[14px] text-[#162A4C] placeholder:text-[#9aa5bd] outline-none transition focus:border-[#162A4C] focus:ring-2 focus:ring-[#162A4C]/15";

  return (
    <main className="grid min-h-screen bg-[#fafafa] lg:grid-cols-[44%_56%]">
      {/* ---------- Left panel ---------- */}
      <aside
        className="relative hidden flex-col justify-between bg-[#162A4C] bg-cover bg-center text-white lg:flex"
        style={{
          backgroundImage: `linear-gradient(rgba(15,29,56,0.9), rgba(15,29,56,0.94)), url(${bgLogin})`,
        }}
      >
        <div className="bg-[#0F1D38]/60 px-10 py-6">
          <Logo />
        </div>

        <div className="px-10 py-10">
          <h1 className="mb-4 text-[40px] font-bold leading-tight tracking-tight">
            Welcome back
          </h1>
          <p className="mb-10 max-w-[380px] text-[16px] leading-8 text-[#dbe4f5]">
            Log in to your TenderMind account and continue managing your tenders
            with confidence.
          </p>

          <ul className="mb-10 space-y-7">
            {features.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex items-center gap-5">
                <span className="flex h-[70px] w-[70px] shrink-0 items-center justify-center rounded-full bg-white/10 text-[#C8A96B]">
                  <Icon size={30} strokeWidth={1.6} />
                </span>
                <div className="max-w-[240px]">
                  <p className="text-[14px] font-bold">{title}</p>
                  <p className="mt-0.5 text-[13px] leading-relaxed text-[#c5d0e6]">
                    {text}
                  </p>
                </div>
              </li>
            ))}
          </ul>

          <div className="flex max-w-[420px] items-start gap-4 rounded-xl border border-white/15 bg-white/5 p-5">
            <Lock size={20} strokeWidth={1.8} className="mt-0.5 shrink-0" />
            <div>
              <p className="text-[14px] font-bold">Your security is our priority</p>
              <p className="mt-0.5 text-[13px] leading-relaxed text-[#c5d0e6]">
                We use enterprise-grade security to protect your data.
              </p>
            </div>
          </div>
        </div>

        <footer className="px-10 pb-10 text-[13px] text-[#c5d0e6]">
          <p className="mb-2">
            © {new Date().getFullYear()} TenderMind. All rights reserved.
          </p>
          <nav className="flex items-center gap-3">
            <a href="/privacy" className="hover:text-white">Privacy Policy</a>
            <span className="text-white/30">|</span>
            <a href="/terms" className="hover:text-white">Terms of Service</a>
            <span className="text-white/30">|</span>
            <a href="/security" className="hover:text-white">Security</a>
          </nav>
        </footer>
      </aside>

      {/* ---------- Right panel ---------- */}
      <section className="relative flex flex-col px-4 py-6 sm:px-8">
        <div className="flex items-center justify-between">
          <div className="lg:invisible">
            <Logo dark />
          </div>

          <label className="relative flex items-center rounded-lg border border-[#e2e6ee] bg-white text-[13px] text-[#162A4C]">
            <Globe size={16} strokeWidth={1.8} className="pointer-events-none absolute left-3" />
            <select
              value={lang}
              onChange={(e) => setLang(e.target.value)}
              className="h-10 appearance-none bg-transparent pl-9 pr-9 font-medium outline-none"
              aria-label="Language"
            >
              <option value="en">English</option>
              <option value="ar">العربية</option>
            </select>
            <ChevronDown size={14} className="pointer-events-none absolute right-3" />
          </label>
        </div>

        <div className="flex flex-1 items-center justify-center py-8">
          <div className="w-full max-w-[540px] rounded-2xl border border-[#ebe8e1] bg-white p-7 shadow-sm sm:p-10">
            <h2 className="mb-2 text-[28px] font-bold tracking-tight text-[#162A4C]">
              Log in to your account
            </h2>
            <p className="mb-8 text-[14px] text-[#4b5f86]">
              Enter your credentials to access TenderMind
            </p>

            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Email */}
              <div>
                <label htmlFor="email" className="mb-2 block text-[13px] font-semibold text-[#162A4C]">
                  Work Email
                </label>
                <div className="relative">
                  <Mail size={18} strokeWidth={1.6} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#6b7a99]" />
                  <input
                    id="email"
                    type="email"
                    required
                    autoComplete="email"
                    placeholder="you@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className={`${inputClass} pr-4`}
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label htmlFor="password" className="text-[13px] font-semibold text-[#162A4C]">
                    Password
                  </label>
                  <a href="/forgot-password" className="text-[12px] font-semibold text-blue-600 hover:underline">
                    Forgot password?
                  </a>
                </div>
                <div className="relative">
                  <Lock size={18} strokeWidth={1.6} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#6b7a99]" />
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    required
                    autoComplete="current-password"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={`${inputClass} pr-12`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-[#6b7a99] hover:text-[#162A4C]"
                  >
                    {showPassword ? <Eye size={18} strokeWidth={1.6} /> : <EyeOff size={18} strokeWidth={1.6} />}
                  </button>
                </div>
              </div>

              {/* Remember */}
              <label className="flex cursor-pointer items-center gap-2.5 text-[13px] font-medium text-[#162A4C]">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  className="h-[18px] w-[18px] rounded accent-[#162A4C]"
                />
                Remember me
              </label>

              <button
                type="submit"
                className="h-[52px] w-full rounded-lg bg-[#162A4C] text-[15px] font-bold text-white transition hover:bg-[#0F1D38] focus:outline-none focus:ring-2 focus:ring-[#162A4C]/40 focus:ring-offset-2"
              >
                Log In
              </button>
            </form>

            {/* Divider */}
            <div className="my-6 flex items-center gap-4 text-[13px] text-[#4b5f86]">
              <span className="h-px flex-1 bg-[#e2e6ee]" />
              or continue with
              <span className="h-px flex-1 bg-[#e2e6ee]" />
            </div>

            <div className="space-y-3">

             {/* مؤقتا عما الباك يتعمل     */}
            <GoogleLogin
            onSuccess={(credentialResponse) => {
                console.log("Google Login Success:", credentialResponse);

                navigate("/dashboard");
            }}
            onError={() => {
                console.log("Google Login Failed");
            }}
            />
            {/*  */}
              <button
                type="button"
                className="flex h-[52px] w-full items-center justify-center gap-3 rounded-lg border border-[#e2e6ee] bg-white text-[14px] font-medium text-[#162A4C] transition hover:bg-[#f5f6f9]"
              >
                <MicrosoftIcon />
                Continue with Microsoft
              </button>
            </div>

            <p className="mt-7 text-center text-[13px] text-[#4b5f86]">
              Don’t have an account?{" "}
              <a href="/contact" className="font-semibold text-blue-600 hover:underline">
                Contact Sales
              </a>
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}

export default Login;
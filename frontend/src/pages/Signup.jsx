import { useState } from "react";
import { Mail, Lock, Eye, EyeOff, User, Check } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import apiClient from "../api/client";
import AuthLayout from "../components/AuthLayout";
import SocialSignIn from "../components/SocialSignIn";
import { inputClass } from "./Login";
import { useT } from "../i18n";

// Mirrors the server rules (app/auth.py password_problem) so users see them before submitting.
const RULES = [
  { id: "len", label: "At least 8 characters", test: (p) => p.length >= 8 },
  { id: "letter", label: "Contains a letter", test: (p) => /[A-Za-z]/.test(p) },
  { id: "digit", label: "Contains a number", test: (p) => /\d/.test(p) },
];

function Signup() {
  const t = useT();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [accountType, setAccountType] = useState("company");

  const rulesOk = RULES.every((r) => r.test(password));
  const matches = confirm.length > 0 && confirm === password;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!rulesOk) return setError(t("Password does not meet the requirements below."));
    if (!matches) return setError(t("Passwords do not match."));
    setLoading(true);
    try {
      await apiClient.signup({ name: name.trim(), email: email.trim(), password, account_type: accountType });
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(t(err?.message || "Sign-up failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout heading={t("Create your account")} intro={t("Start analysing tenders with evidence-backed requirements and bid decisions.")}>
      <h2 className="mb-2 text-[28px] font-bold tracking-tight text-[#162A4C]">{t("Sign up")}</h2>
      <p className="mb-6 text-[14px] text-[#4b5f86]">{t("Use your work email, or continue with Google or Microsoft")}</p>

      <SocialSignIn next="/dashboard" />

      <div className="my-6 flex items-center gap-4 text-[13px] text-[#4b5f86]">
        <span className="h-px flex-1 bg-[#e2e6ee]" />
        {t("or sign up with email")}
        <span className="h-px flex-1 bg-[#e2e6ee]" />
      </div>

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <fieldset data-testid="account-type">
          <legend className="mb-2 block text-[13px] font-semibold text-[#162A4C]">{t("Account type")}</legend>
          <div className="grid grid-cols-2 gap-2">
            {[["company", "Company", "A tender team with members, votes and approvals"],
              ["individual", "Individual professional", "Your own profile, certificates and tenders"]].map(([v, label, hint]) => (
              <label key={v} className={`cursor-pointer rounded-xl border p-3 text-[13px] ${accountType === v ? "border-[#162A4C] bg-[#eef2f8]" : "border-[#e2e6ee]"}`}>
                <input type="radio" name="account_type" value={v} checked={accountType === v} onChange={() => setAccountType(v)} className="me-2" />
                <b className="text-[#162A4C]">{t(label)}</b>
                <span className="mt-1 block text-[12px] text-[#4b5f86]">{t(hint)}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <div>
          <label htmlFor="name" className="mb-2 block text-[13px] font-semibold text-[#162A4C]">{t("Full name")} <span className="font-normal text-[#98a2b3]">{t("(optional)")}</span></label>
          <div className="relative">
            <User size={18} strokeWidth={1.6} className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-[#6b7a99]" />
            <input id="name" autoComplete="name" placeholder={t("Your name")} value={name}
              onChange={(e) => setName(e.target.value)} className={`${inputClass} pe-4`} />
          </div>
        </div>

        <div>
          <label htmlFor="email" className="mb-2 block text-[13px] font-semibold text-[#162A4C]">{t("Work Email")}</label>
          <div className="relative">
            <Mail size={18} strokeWidth={1.6} className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-[#6b7a99]" />
            <input id="email" type="email" required autoComplete="email" placeholder="you@company.com"
              value={email} onChange={(e) => setEmail(e.target.value)} className={`${inputClass} pe-4`} />
          </div>
        </div>

        <div>
          <label htmlFor="password" className="mb-2 block text-[13px] font-semibold text-[#162A4C]">{t("Password")}</label>
          <div className="relative">
            <Lock size={18} strokeWidth={1.6} className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-[#6b7a99]" />
            <input id="password" type={showPassword ? "text" : "password"} required autoComplete="new-password"
              placeholder={t("Create a password")} value={password} onChange={(e) => setPassword(e.target.value)}
              className={`${inputClass} pe-12`} />
            <button type="button" onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? t("Hide password") : t("Show password")}
              className="absolute end-4 top-1/2 -translate-y-1/2 text-[#6b7a99] hover:text-[#162A4C]">
              {showPassword ? <Eye size={18} strokeWidth={1.6} /> : <EyeOff size={18} strokeWidth={1.6} />}
            </button>
          </div>
          <ul className="mt-2 grid grid-cols-1 gap-1 sm:grid-cols-3">
            {RULES.map((r) => {
              const ok = r.test(password);
              return (
                <li key={r.id} data-testid={`rule-${r.id}`} className={`flex items-center gap-1.5 text-[12px] ${ok ? "text-[#2E7D5B]" : "text-[#98a2b3]"}`}>
                  <Check size={13} className={ok ? "" : "opacity-30"} /> {t(r.label)}
                </li>
              );
            })}
          </ul>
        </div>

        <div>
          <label htmlFor="confirm" className="mb-2 block text-[13px] font-semibold text-[#162A4C]">{t("Confirm password")}</label>
          <div className="relative">
            <Lock size={18} strokeWidth={1.6} className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-[#6b7a99]" />
            <input id="confirm" type={showPassword ? "text" : "password"} required autoComplete="new-password"
              placeholder={t("Repeat the password")} value={confirm} onChange={(e) => setConfirm(e.target.value)}
              className={`${inputClass} pe-4`} />
          </div>
          {confirm && !matches && <p className="mt-1 text-[12px] text-red-600">{t("Passwords do not match")}</p>}
        </div>

        {error && (
          <p data-testid="signup-error" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">{error}</p>
        )}

        <button type="submit" disabled={loading}
          className="h-[52px] w-full rounded-lg bg-[#162A4C] text-[15px] font-bold text-white transition hover:bg-[#0F1D38] disabled:opacity-60">
          {loading ? t("Creating account...") : t("Create account")}
        </button>
      </form>

      <p className="mt-7 text-center text-[13px] text-[#4b5f86]">
        {t("Already have an account?")}{" "}
        <Link to="/login" className="font-semibold text-blue-600 hover:underline">{t("Log in")}</Link>
      </p>
    </AuthLayout>
  );
}

export default Signup;

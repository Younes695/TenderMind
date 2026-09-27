import { useState } from "react";
import { Mail, Lock, Eye, EyeOff } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import apiClient from "../api/client";
import AuthLayout from "../components/AuthLayout";
import SocialSignIn, { AUTH_ERRORS } from "../components/SocialSignIn";

export const inputClass =
  "h-[54px] w-full rounded-lg border border-[#e2e6ee] bg-white pl-11 text-[14px] text-[#162A4C] placeholder:text-[#9aa5bd] outline-none transition focus:border-[#162A4C] focus:ring-2 focus:ring-[#162A4C]/15";

function Login() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const oauthError = params.get("auth_error");
  const [error, setError] = useState(oauthError ? AUTH_ERRORS[oauthError] || "Sign-in failed." : "");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await apiClient.login({ email, password });
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err?.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout heading="Welcome back" intro="Log in to your TenderMind account and continue managing your tenders with confidence.">
      <h2 className="mb-2 text-[28px] font-bold tracking-tight text-[#162A4C]">Log in to your account</h2>
      <p className="mb-8 text-[14px] text-[#4b5f86]">Enter your credentials to access TenderMind</p>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label htmlFor="email" className="mb-2 block text-[13px] font-semibold text-[#162A4C]">Work Email</label>
          <div className="relative">
            <Mail size={18} strokeWidth={1.6} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#6b7a99]" />
            <input id="email" type="email" required autoComplete="email" placeholder="you@company.com"
              value={email} onChange={(e) => setEmail(e.target.value)} className={`${inputClass} pr-4`} />
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <label htmlFor="password" className="text-[13px] font-semibold text-[#162A4C]">Password</label>
            <a href="/forgot-password" className="text-[12px] font-semibold text-blue-600 hover:underline">Forgot password?</a>
          </div>
          <div className="relative">
            <Lock size={18} strokeWidth={1.6} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#6b7a99]" />
            <input id="password" type={showPassword ? "text" : "password"} required autoComplete="current-password"
              placeholder="Enter your password" value={password} onChange={(e) => setPassword(e.target.value)}
              className={`${inputClass} pr-12`} />
            <button type="button" onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-[#6b7a99] hover:text-[#162A4C]">
              {showPassword ? <Eye size={18} strokeWidth={1.6} /> : <EyeOff size={18} strokeWidth={1.6} />}
            </button>
          </div>
        </div>

        <label className="flex cursor-pointer items-center gap-2.5 text-[13px] font-medium text-[#162A4C]">
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)}
            className="h-[18px] w-[18px] rounded accent-[#162A4C]" />
          Remember me
        </label>

        {error && (
          <p data-testid="login-error" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">{error}</p>
        )}

        <button type="submit" disabled={loading}
          className="h-[52px] w-full rounded-lg bg-[#162A4C] text-[15px] font-bold text-white transition hover:bg-[#0F1D38] focus:outline-none focus:ring-2 focus:ring-[#162A4C]/40 focus:ring-offset-2">
          {loading ? "Signing in..." : "Log In"}
        </button>
      </form>

      <div className="my-6 flex items-center gap-4 text-[13px] text-[#4b5f86]">
        <span className="h-px flex-1 bg-[#e2e6ee]" />
        or continue with
        <span className="h-px flex-1 bg-[#e2e6ee]" />
      </div>

      <SocialSignIn next="/dashboard" />

      <p className="mt-7 text-center text-[13px] text-[#4b5f86]">
        Don’t have an account?{" "}
        <Link to="/signup" className="font-semibold text-blue-600 hover:underline">Sign up</Link>
      </p>
    </AuthLayout>
  );
}

export default Login;

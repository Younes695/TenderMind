import { useEffect, useState } from "react";
import apiClient from "../api/client";
import { useT } from "../i18n";

export function GoogleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4.1 7.1-10.1 7.1-17.5z" />
      <path fill="#FBBC05" d="M10.5 28.7c-.5-1.4-.8-3-.8-4.7s.3-3.2.8-4.7l-7.9-6.1C.9 16.4 0 20.1 0 24s.9 7.6 2.6 10.8l7.9-6.1z" />
      <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.8 2.3-8.4 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z" />
    </svg>
  );
}

export function MicrosoftIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 21 21" aria-hidden="true">
      <rect x="1" y="1" width="9" height="9" fill="#F25022" />
      <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
      <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
      <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
    </svg>
  );
}

// Messages for ?auth_error=<code> set by the server after a failed sign-in.
export const AUTH_ERRORS = {
  google_not_configured: "Google sign-in is not configured on this server yet.",
  microsoft_not_configured: "Microsoft sign-in is not configured on this server yet.",
  cancelled: "Sign-in was cancelled.",
  invalid_state: "The sign-in session expired. Please try again.",
  token_exchange_failed: "Could not complete sign-in with the provider. Please try again.",
  invalid_token: "The provider's response could not be verified.",
  email_not_verified: "Your Google email address is not verified.",
  no_email: "The provider did not share an email address.",
  signup_disabled: "New accounts are not accepted on this server.",
  account_exists: "An account with this email already exists. Sign in the way you created it (email and password, or the original provider).",
};

const PROVIDERS = [
  { id: "google", label: "Google", Icon: GoogleIcon },
  { id: "microsoft", label: "Microsoft", Icon: MicrosoftIcon },
];

/** "Continue with Google / Microsoft" - full-page redirect to the server's OAuth start. */
export default function SocialSignIn({ next = "/dashboard" }) {
  const t = useT();
  const [available, setAvailable] = useState(null);

  useEffect(() => {
    apiClient.getAuthProviders().then(setAvailable).catch(() => setAvailable({}));
  }, []);

  return (
    <div className="space-y-3">
      {PROVIDERS.map(({ id, label, Icon }) => {
        const enabled = !!available?.[id];
        const href = apiClient.apiUrl(`/api/auth/oauth/${id}/start?next=${encodeURIComponent(next)}`);
        const cls = "flex h-[52px] w-full items-center justify-center gap-3 rounded-lg border border-[#e2e6ee] bg-white text-[14px] font-medium text-[#162A4C] transition";
        return enabled ? (
          <a key={id} href={href} data-testid={`oauth-${id}`} className={`${cls} hover:bg-[#f5f6f9]`}>
            <Icon /> {t("Continue with {label}", { label })}
          </a>
        ) : (
          <button key={id} type="button" disabled data-testid={`oauth-${id}`} title={t("{label} sign-in is not configured on this server yet", { label })}
            className={`${cls} cursor-not-allowed opacity-50`}>
            <Icon /> {t("Continue with {label}", { label })}
          </button>
        );
      })}
      {available && !available.google && !available.microsoft && (
        <p className="text-center text-[12px] text-[#98a2b3]">{t("Google and Microsoft sign-in will appear once configured by the administrator.")}</p>
      )}
    </div>
  );
}

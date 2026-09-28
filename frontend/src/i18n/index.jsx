import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

/*
 * Stage 5I - language (English / Arabic) and theme (light / dark / system).
 *
 * Translations: t("English text") returns the Arabic string when the language
 * is Arabic and one exists, otherwise the English text - so an untranslated
 * string never shows up blank. Dictionaries live in ./ar/*.js (one file per
 * area of the app) and are merged here. {name} placeholders are filled from vars.
 */
const modules = import.meta.glob("./ar/*.js", { eager: true });
const AR = Object.assign({}, ...Object.values(modules).map((m) => m.default || {}));

const STORAGE_KEY = "tm.prefs";

function readPrefs() {
  try {
    return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}") || {};
  } catch {
    return {};
  }
}

function writePrefs(p) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
  } catch {
    /* private mode / blocked storage: preferences just aren't remembered */
  }
}

export function translate(lang, text, vars) {
  let s = lang === "ar" && AR[text] ? AR[text] : text.split("|")[0]; // "Open|status": context hint, not shown
  if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (vars[k] ?? m));
  return s;
}

const PrefsContext = createContext({
  lang: "en", setLang: () => {}, theme: "light", setTheme: () => {}, dark: false,
  t: (text, vars) => translate("en", text, vars),
});

export function PreferencesProvider({ children }) {
  const initial = typeof window !== "undefined" ? readPrefs() : {};
  const [lang, setLangState] = useState(initial.lang === "ar" ? "ar" : "en");
  const [theme, setThemeState] = useState(["light", "dark", "system"].includes(initial.theme) ? initial.theme : "light");
  const [systemDark, setSystemDark] = useState(
    typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)").matches : false);

  useEffect(() => {
    if (!window.matchMedia) return undefined;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const on = (e) => setSystemDark(e.matches);
    mq.addEventListener?.("change", on);
    return () => mq.removeEventListener?.("change", on);
  }, []);

  const dark = theme === "dark" || (theme === "system" && systemDark);

  useEffect(() => {
    const el = document.documentElement;
    el.lang = lang;
    el.dir = lang === "ar" ? "rtl" : "ltr";
    el.classList.toggle("dark", dark);
    writePrefs({ lang, theme });
  }, [lang, theme, dark]);

  const setLang = useCallback((l) => setLangState(l === "ar" ? "ar" : "en"), []);
  const setTheme = useCallback((t) => setThemeState(["light", "dark", "system"].includes(t) ? t : "light"), []);
  const t = useCallback((text, vars) => translate(lang, text, vars), [lang]);
  const value = useMemo(() => ({ lang, setLang, theme, setTheme, dark, t }), [lang, setLang, theme, setTheme, dark, t]);
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

export function usePrefs() {
  return useContext(PrefsContext);
}

/** Shorthand used by every component: const t = useT(); t("Start processing") */
export function useT() {
  return useContext(PrefsContext).t;
}

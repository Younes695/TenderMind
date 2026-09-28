import { translate } from "../i18n";

/** Ask before deleting something the user uploaded (Stage 5H: a mis-click used
 *  to delete a file straight away). */
export function confirmRemoval(name, what = "file") {
  const lang = document.documentElement.lang === "ar" ? "ar" : "en";
  const label = name ? `“${name}”` : translate(lang, `this ${what}`);
  return window.confirm(translate(lang, "Delete {label}?\n\nIt will be removed from this tender and cannot be undone.", { label }));
}

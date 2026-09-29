import { useEffect, useState } from "react";
import apiClient from "./api/client";

/** The account type: "company" (team, department votes, approvals) or "individual" (one professional).
 *  Loaded once and shared; changing it in Settings updates every open component. */
let cached = null;
let loading = null;
const listeners = new Set();

function load() {
  if (!loading) {
    loading = apiClient.getAccount()
      .then((d) => { cached = d?.account_type === "individual" ? "individual" : "company"; })
      .catch(() => { cached = "company"; })
      .finally(() => { listeners.forEach((fn) => fn(cached)); });
  }
  return loading;
}

export function useAccountType() {
  const [type, setType] = useState(cached || "company");
  useEffect(() => {
    listeners.add(setType);
    if (cached) setType(cached);
    else load();
    return () => listeners.delete(setType);
  }, []);
  return type;
}

export async function setAccountType(type) {
  const d = await apiClient.setAccount({ account_type: type });
  cached = d.account_type;
  listeners.forEach((fn) => fn(cached));
  return cached;
}

/** For tests. */
export function resetAccountCache() {
  cached = null;
  loading = null;
}

import { useEffect, useState } from "react";
import { Navigate, Outlet } from "react-router-dom";
import apiClient from "../api/client";
import { useT } from "../i18n";

export default function ProtectedRoute() {
  const t = useT();
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    let mounted = true;

    apiClient
      .getCurrentUser()
      .then(() => {
        if (mounted) setStatus("authenticated");
      })
      .catch(() => {
        if (mounted) setStatus("unauthenticated");
      });

    return () => {
      mounted = false;
    };
  }, []);

  if (status === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-slate-500">{t("Checking session...")}</p>
      </div>
    );
  }

  if (status === "unauthenticated") {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
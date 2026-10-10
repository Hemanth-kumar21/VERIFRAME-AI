"use client";

import { useEffect, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type ThemeMode = "system" | "light" | "dark";

export default function AppPreferences() {
  const [theme, setTheme] = useState<ThemeMode>("system");
  const [backend, setBackend] = useState<"checking" | "online" | "offline">("checking");
  const [providerOnline, setProviderOnline] = useState<boolean | null>(null);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      const stored = window.localStorage.getItem("very-frame-theme");
      if (stored === "light" || stored === "dark" || stored === "system") setTheme(stored);
    }, 0);
    return () => window.clearTimeout(timeout);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const applyTheme = () => {
      const mode = theme === "system" ? (media.matches ? "dark" : "light") : theme;
      root.dataset.theme = mode;
      root.style.colorScheme = mode;
    };
    applyTheme();
    if (theme === "system") media.addEventListener("change", applyTheme);
    return () => media.removeEventListener("change", applyTheme);
  }, [theme]);

  useEffect(() => {
    let active = true;
    const checkHealth = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/health`, { signal: AbortSignal.timeout(5000) });
        if (!response.ok) throw new Error("Backend health check failed.");
        const payload = (await response.json()) as { status?: string; llm?: string };
        if (!active) return;
        setBackend(payload.status === "ok" ? "online" : "offline");
        setProviderOnline(payload.llm === "online");
      } catch {
        if (!active) return;
        setBackend("offline");
        setProviderOnline(null);
      }
    };
    void checkHealth();
    const interval = window.setInterval(() => void checkHealth(), 60_000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  const cycleTheme = () => {
    const next: ThemeMode =
      theme === "system" ? "light" : theme === "light" ? "dark" : "system";
    setTheme(next);
    window.localStorage.setItem("very-frame-theme", next);
  };

  const providerNotice =
    backend === "offline"
      ? "Backend unavailable. Image investigation cannot run right now."
      : backend === "online" && providerOnline === false
        ? "The configured AI provider is offline; the backend may use its fixed fallback pipeline."
        : backend === "online"
          ? "Image investigation service is reachable."
          : null;

  return (
    <div className="border-b border-white/10 bg-slate-950/50 px-4 py-2 text-sm text-slate-300">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2">
        <p role="status" aria-live="polite">
          {backend === "checking"
            ? "Checking investigation service…"
            : providerNotice}
        </p>
        <button
          type="button"
          onClick={cycleTheme}
          className="min-h-11 rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-100 hover:border-sky-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300"
          aria-label={`Theme preference: ${theme}. Activate to change theme.`}
        >
          Theme: {theme}
        </button>
      </div>
    </div>
  );
}

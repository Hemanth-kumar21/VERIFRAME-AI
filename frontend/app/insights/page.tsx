"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Insights = {
  total_analyses: number;
  verdict_distribution: Record<string, number>;
  inconclusive_share: number;
  mode_distribution: Record<string, number>;
  average_latency_ms: number | null;
  wrong_result_reports: number;
};

async function fetchInsights(token: string): Promise<Insights> {
  const response = await fetch(`${API_BASE_URL}/api/insights`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status === 401) throw new Error("The access token was not accepted.");
  if (response.status === 503) throw new Error("Aggregate insights are disabled by the server operator.");
  if (!response.ok) throw new Error("Insights are currently unavailable.");
  const payload = (await response.json()) as Partial<Insights>;
  if (
    typeof payload.total_analyses !== "number" ||
    typeof payload.inconclusive_share !== "number" ||
    typeof payload.verdict_distribution !== "object" ||
    payload.verdict_distribution === null ||
    typeof payload.mode_distribution !== "object" ||
    payload.mode_distribution === null ||
    (payload.average_latency_ms !== null && typeof payload.average_latency_ms !== "number") ||
    typeof payload.wrong_result_reports !== "number"
  ) {
    throw new Error("The backend returned an invalid insights response.");
  }
  return payload as Insights;
}

export default function InsightsPage() {
  const [accessToken, setAccessToken] = useState("");
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadInsights = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const token = accessToken.trim();
    if (!token) {
      setError("Enter the server-configured insights access token.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      setInsights(await fetchInsights(token));
    } catch (loadError) {
      setInsights(null);
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Insights are currently unavailable.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen px-4 py-8 text-slate-100 sm:px-6 sm:py-12">
      <section className="mx-auto max-w-5xl space-y-6">
        <header className="rounded-3xl border border-sky-400/20 bg-slate-950/50 p-6 sm:p-8">
          <p className="text-xs uppercase tracking-[0.3em] text-sky-300">Very Frame AI</p>
          <h1 className="mt-3 text-3xl font-semibold text-white">Aggregate insights</h1>
          <p className="mt-4 text-sm leading-6 text-slate-300">
            Only aggregate counts are displayed. Uploaded images and individual results are never shown here.
          </p>
        </header>

        <form onSubmit={(event) => void loadInsights(event)} className="space-y-3 rounded-2xl border border-slate-700 bg-slate-900/70 p-5">
          <label htmlFor="insights-token" className="block text-sm font-medium text-slate-100">
            Server-configured access token
          </label>
          <input
            id="insights-token"
            type="password"
            autoComplete="off"
            value={accessToken}
            onChange={(event) => setAccessToken(event.target.value)}
            className="min-h-11 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-300"
          />
          <button
            type="submit"
            disabled={loading}
            className="min-h-11 rounded-xl bg-sky-500 px-4 py-2 font-semibold text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300 disabled:opacity-60"
          >
            {loading ? "Loading…" : insights ? "Refresh insights" : "View insights"}
          </button>
        </form>

        {loading && (
          <p role="status" aria-live="polite" className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5 text-slate-300">
            Loading aggregate insights…
          </p>
        )}
        {error && (
          <p role="alert" className="rounded-2xl border border-amber-400/30 bg-amber-500/10 p-5 text-amber-100">
            {error}
          </p>
        )}
        {insights && !loading && (
          <dl className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5">
              <dt className="text-sm text-slate-400">Total analyses</dt>
              <dd className="mt-2 text-3xl font-semibold text-white">{insights.total_analyses}</dd>
            </div>
            {Object.entries(insights.verdict_distribution).map(([verdict, count]) => (
              <div key={verdict} className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5">
                <dt className="break-words text-sm text-slate-400">{verdict}</dt>
                <dd className="mt-2 text-3xl font-semibold text-white">{count}</dd>
              </div>
            ))}
            <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5">
              <dt className="text-sm text-slate-400">Inconclusive share</dt>
              <dd className="mt-2 text-3xl font-semibold text-white">{insights.inconclusive_share}%</dd>
            </div>
            <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5">
              <dt className="text-sm text-slate-400">Average analysis latency</dt>
              <dd className="mt-2 text-3xl font-semibold text-white">
                {insights.average_latency_ms === null ? "Not reported" : `${insights.average_latency_ms} ms`}
              </dd>
            </div>
            <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5">
              <dt className="text-sm text-slate-400">Incorrect-result reports</dt>
              <dd className="mt-2 text-3xl font-semibold text-white">{insights.wrong_result_reports}</dd>
            </div>
            {Object.entries(insights.mode_distribution).map(([mode, count]) => (
              <div key={mode} className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5">
                <dt className="break-words text-sm text-slate-400">Mode: {mode}</dt>
                <dd className="mt-2 text-3xl font-semibold text-white">{count}</dd>
              </div>
            ))}
          </dl>
        )}
        <Link href="/" className="inline-flex min-h-11 items-center rounded-xl border border-slate-700 bg-slate-950 px-4 py-2 text-slate-100 hover:border-sky-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-300">
          Back to upload
        </Link>
      </section>
    </main>
  );
}

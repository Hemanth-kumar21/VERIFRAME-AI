"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Sample = {
  id?: string;
  name?: string;
  media_type?: string;
  category?: string;
  description?: string;
};

export default function SamplesPage() {
  const [samples, setSamples] = useState<Sample[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void fetch(`${API_BASE_URL}/api/samples`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Samples are unavailable.");
        const payload = (await response.json()) as { samples?: unknown };
        if (!Array.isArray(payload.samples)) throw new Error("Invalid sample response.");
        setSamples(payload.samples.filter((item): item is Sample => typeof item === "object" && item !== null));
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      });
    return () => controller.abort();
  }, []);

  return (
    <main className="min-h-screen px-4 py-8 text-slate-100 sm:px-6 sm:py-12">
      <section className="mx-auto max-w-5xl space-y-6">
        <header className="rounded-3xl border border-sky-400/20 bg-slate-950/50 p-6 sm:p-8">
          <p className="text-xs uppercase tracking-[0.3em] text-sky-300">Very Frame AI</p>
          <h1 className="mt-3 text-3xl font-semibold text-white">Sample gallery</h1>
          <p className="mt-4 text-sm leading-6 text-slate-300">
            Samples are provided by the backend. Labels are shown only when returned with the sample.
          </p>
        </header>
        {error ? (
          <p role="alert" className="rounded-2xl border border-amber-400/30 bg-amber-500/10 p-5 text-amber-100">
            Samples are currently unavailable. Try again later.
          </p>
        ) : samples === null ? (
          <p role="status" aria-live="polite" className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5 text-slate-300">
            Loading samples…
          </p>
        ) : samples.length === 0 ? (
          <p className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5 text-slate-300">
            No samples are currently available. No demo media or ground-truth labels have been fabricated.
          </p>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2">
            {samples.map((sample, index) => (
              <li key={sample.id ?? `${sample.name ?? "sample"}-${index}`} className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5">
                <h2 className="break-words font-semibold text-white">{sample.name ?? "Sample media"}</h2>
                <p className="mt-2 text-sm text-slate-300">
                  {sample.category ?? "Category not provided"}
                  {sample.media_type ? ` · ${sample.media_type}` : ""}
                </p>
                {sample.description && <p className="mt-2 break-words text-sm text-slate-400">{sample.description}</p>}
              </li>
            ))}
          </ul>
        )}
        <Link href="/" className="inline-flex min-h-11 items-center rounded-xl border border-slate-700 bg-slate-950 px-4 py-2 text-slate-100 hover:border-sky-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-300">
          Back to upload
        </Link>
      </section>
    </main>
  );
}

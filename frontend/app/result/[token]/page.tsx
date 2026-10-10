import { Suspense } from "react";
import ResultShell from "@/components/result-shell";

export default function ResultPage() {
  return (
    <main className="min-h-screen px-6 py-10 text-slate-100">
      <Suspense fallback={<div className="mx-auto max-w-4xl rounded-3xl border border-slate-700 bg-slate-900/70 p-8 text-lg">Loading result…</div>}>
        <ResultShell />
      </Suspense>
    </main>
  );
}
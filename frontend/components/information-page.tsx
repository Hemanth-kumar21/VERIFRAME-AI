import Link from "next/link";
import { ReactNode } from "react";

export function InformationPage({
  title,
  intro,
  children,
}: {
  title: string;
  intro: string;
  children: ReactNode;
}) {
  return (
    <main className="min-h-screen px-4 py-8 text-slate-100 sm:px-6 sm:py-12">
      <article className="mx-auto max-w-4xl space-y-6">
        <header className="rounded-3xl border border-sky-400/20 bg-slate-950/50 p-6 sm:p-8">
          <p className="text-xs uppercase tracking-[0.3em] text-sky-300">Very Frame AI</p>
          <h1 className="mt-3 break-words text-3xl font-semibold text-white sm:text-4xl">{title}</h1>
          <p className="mt-4 break-words text-base leading-7 text-slate-300">{intro}</p>
        </header>
        <div className="space-y-5">{children}</div>
        <Link
          href="/"
          className="inline-flex min-h-11 items-center rounded-xl border border-slate-700 bg-slate-950 px-4 py-2 font-medium text-slate-100 hover:border-sky-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300"
        >
          Back to upload
        </Link>
      </article>
    </main>
  );
}

export function InformationSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 sm:p-6">
      <h2 className="break-words text-xl font-semibold text-white">{title}</h2>
      <div className="mt-3 break-words text-sm leading-6 text-slate-300">{children}</div>
    </section>
  );
}

import Link from "next/link";

const links = [
  { href: "/", label: "Home" },
  { href: "/cases", label: "Workspace & Cases" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/limitations", label: "Limitations" },
  { href: "/privacy", label: "Privacy" },
  { href: "/samples", label: "Samples" },
  { href: "/insights", label: "Insights" },
];

export default function SiteNavigation() {
  return (
    <nav
      aria-label="Main navigation"
      className="border-b border-white/10 bg-slate-950/70 px-4 py-2"
    >
      <ul className="mx-auto flex max-w-6xl flex-wrap gap-x-2 gap-y-1">
        {links.map(({ href, label }) => (
          <li key={href}>
            <Link
              href={href}
              className="inline-flex min-h-11 items-center rounded-lg px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300"
            >
              {label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

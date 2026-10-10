"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type CaseItem = {
  case_id: string;
  title: string;
  description: string;
  status: "open" | "in_review" | "concluded" | "archived" | string;
  priority: "low" | "normal" | "high" | "urgent" | string;
  tags: string[];
  investigator: string;
  item_count?: number;
  created_at: string;
  updated_at: string;
};

export default function CasesDashboardPage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [search, setSearch] = useState<string>("");
  const [showModal, setShowModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("normal");
  const [tagsInput, setTagsInput] = useState("");
  const [investigator, setInvestigator] = useState("Lead Forensic Examiner");

  const fetchCases = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`${API_BASE_URL}/api/cases`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setCases(data.cases || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load cases.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, []);

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    try {
      setCreating(true);
      const tags = tagsInput
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      const res = await fetch(`${API_BASE_URL}/api/cases`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim(),
          priority,
          tags,
          investigator: investigator.trim(),
        }),
      });
      if (!res.ok) throw new Error("Could not create case");
      const created = await res.json();
      setShowModal(false);
      setTitle("");
      setDescription("");
      setTagsInput("");
      fetchCases();
    } catch (err) {
      alert("Error creating case. Please check backend connection.");
    } finally {
      setCreating(false);
    }
  };

  const filteredCases = cases.filter((c) => {
    if (filter !== "all" && c.status !== filter) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        c.title.toLowerCase().includes(q) ||
        c.case_id.toLowerCase().includes(q) ||
        c.description.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const totalItems = cases.reduce((sum, c) => sum + (c.item_count || 0), 0);
  const activeCases = cases.filter((c) => c.status === "open" || c.status === "in_review").length;

  return (
    <main className="min-h-screen px-4 py-8 sm:px-6 lg:px-8 text-slate-100">
      <div className="mx-auto max-w-6xl space-y-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-white/10 pb-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex h-2.5 w-2.5 rounded-full bg-sky-400 scan-indicator" />
              <span className="text-xs font-semibold uppercase tracking-widest text-sky-400">
                Case Management & Cross-Media Analysis
              </span>
            </div>
            <h1 className="mt-1 text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
              Investigation Workspace
            </h1>
            <p className="mt-2 text-sm text-slate-400 max-w-2xl">
              Organize multiple digital media assets into structured forensic investigations.
              Automatically correlate capture chronologies, detect contradiction flags, and generate court-ready dossiers.
            </p>
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="inline-flex items-center justify-center rounded-xl bg-sky-500 px-5 py-3 text-sm font-semibold text-slate-950 shadow-lg shadow-sky-500/20 hover:bg-sky-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400 transition"
          >
            + New Investigation Case
          </button>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
            <p className="text-xs font-medium uppercase tracking-wider text-slate-400">Active Investigations</p>
            <p className="mt-2 text-3xl font-bold text-white">{activeCases}</p>
            <p className="mt-1 text-xs text-slate-500">{cases.length} total recorded cases</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
            <p className="text-xs font-medium uppercase tracking-wider text-slate-400">Attached Evidence Items</p>
            <p className="mt-3 text-3xl font-bold text-sky-400">{totalItems}</p>
            <p className="mt-1 text-xs text-slate-500">Cryptographically fingerprinted (SHA-256)</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
            <p className="text-xs font-medium uppercase tracking-wider text-slate-400">Correlation Engine</p>
            <p className="mt-2 text-sm font-semibold text-emerald-400 flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-400"></span> Active & Ready
            </p>
            <p className="mt-2 text-xs text-slate-400">Automated sensor, timestamp & verdict divergence auditing</p>
          </div>
        </div>

        {/* Search & Filter Bar */}
        <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
          <div className="w-full sm:w-80">
            <input
              type="text"
              placeholder="Search cases by ID, title, keyword…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-slate-800 bg-slate-950/70 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-400 focus:outline-none"
            />
          </div>
          <div className="flex items-center gap-2 overflow-x-auto w-full sm:w-auto pb-1">
            {["all", "open", "in_review", "concluded"].map((st) => (
              <button
                key={st}
                onClick={() => setFilter(st)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold uppercase tracking-wider transition ${
                  filter === st
                    ? "bg-sky-500 text-slate-950"
                    : "bg-slate-900/80 text-slate-400 hover:text-slate-200 border border-slate-800"
                }`}
              >
                {st.replace("_", " ")}
              </button>
            ))}
          </div>
        </div>

        {/* Cases List */}
        {loading ? (
          <div className="rounded-3xl border border-slate-800 bg-slate-900/40 p-12 text-center text-slate-400">
            <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-sky-400 border-t-transparent mb-3" />
            <p>Loading investigation workspace cases…</p>
          </div>
        ) : filteredCases.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-slate-800 bg-slate-900/30 p-12 text-center">
            <h3 className="text-lg font-semibold text-slate-300">No matching investigation cases found</h3>
            <p className="mt-1 text-sm text-slate-500 max-w-md mx-auto">
              Create a new case to start attaching and cross-correlating image and video evidence.
            </p>
            <button
              onClick={() => setShowModal(true)}
              className="mt-5 rounded-xl bg-sky-500 px-4 py-2.5 text-sm font-semibold text-slate-950 hover:bg-sky-400 transition"
            >
              + Create First Case
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredCases.map((c) => {
              const isUrgent = c.priority === "high" || c.priority === "urgent";
              return (
                <div
                  key={c.case_id}
                  className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 flex flex-col justify-between hover:border-slate-700 transition"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-semibold text-sky-400 bg-sky-950/60 px-2 py-1 rounded border border-sky-800/40">
                        {c.case_id}
                      </span>
                      <div className="flex items-center gap-2">
                        {isUrgent && (
                          <span className="rounded-full bg-red-950/80 border border-red-800/60 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-red-300">
                            {c.priority}
                          </span>
                        )}
                        <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-300">
                          {c.status.replace("_", " ")}
                        </span>
                      </div>
                    </div>

                    <h2 className="mt-3 text-lg font-semibold text-white line-clamp-1">{c.title}</h2>
                    <p className="mt-1 text-xs text-slate-400 line-clamp-2">
                      {c.description || "No case description provided."}
                    </p>

                    {c.tags && c.tags.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {c.tags.map((tag) => (
                          <span
                            key={tag}
                            className="rounded-md bg-slate-950/80 px-2 py-0.5 text-[11px] text-slate-400 border border-slate-800"
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="mt-6 pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                    <div>
                      <span className="font-semibold text-slate-300">{c.item_count || 0}</span> evidence items attached
                    </div>
                    <Link
                      href={`/cases/${c.case_id}`}
                      className="inline-flex items-center gap-1 font-semibold text-sky-400 hover:text-sky-300"
                    >
                      Open Case Workspace &rarr;
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Create Case Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-3xl border border-slate-700 bg-slate-900 p-6 sm:p-8 shadow-2xl">
            <h2 className="text-xl font-bold text-white">Initialize Investigation Case</h2>
            <p className="mt-1 text-xs text-slate-400">
              Create a structured container for cross-correlating forensic evidence items.
            </p>

            <form onSubmit={handleCreateCase} className="mt-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Case Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Disputed Viral Video & Thumbnail Comparison"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-400 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Description / Incident Details
                </label>
                <textarea
                  rows={3}
                  placeholder="Context of allegations, source URLs, disputed claims…"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-400 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                    Priority
                  </label>
                  <select
                    value={priority}
                    onChange={(e) => setPriority(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none"
                  >
                    <option value="low">Low</option>
                    <option value="normal">Normal</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                    Investigator
                  </label>
                  <input
                    type="text"
                    value={investigator}
                    onChange={(e) => setInvestigator(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Tags (comma separated)
                </label>
                <input
                  type="text"
                  placeholder="deepfake, viral, election, audio-visual"
                  value={tagsInput}
                  onChange={(e) => setTagsInput(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-400 focus:outline-none"
                />
              </div>

              <div className="mt-6 flex items-center justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="rounded-xl px-4 py-2 text-sm font-semibold text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="rounded-xl bg-sky-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-sky-400 transition disabled:opacity-60"
                >
                  {creating ? "Initializing…" : "Create Case"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}

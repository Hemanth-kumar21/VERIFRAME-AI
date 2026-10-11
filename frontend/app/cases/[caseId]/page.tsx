"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type CaseData = {
  case_id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  tags: string[];
  investigator: string;
  notes: Array<{ id: string; timestamp: string; author: string; content: string }>;
  created_at: string;
  updated_at: string;
};

type ItemData = {
  id: number;
  token: string;
  item_type: string;
  label: string;
  sha256: string;
  notes: string;
  added_at: string;
  result?: {
    verdict: string;
    evidence_strength: string;
    agreement: string;
    mode: string;
    created_at?: string;
  } | null;
};

type Contradiction = {
  type: string;
  severity: string;
  affected_items: string[];
  description: string;
};

type TimelineEntry = {
  token: string;
  label: string;
  timestamp: string;
  verdict: string;
  item_type: string;
  camera?: string | null;
  software?: string | null;
  sha256: string;
};

type CorrelationData = {
  total_items: number;
  timeline: TimelineEntry[];
  verdict_summary: Record<string, number>;
  divergence_status: string;
  detected_cameras: string[];
  detected_softwares: string[];
  contradictions: Contradiction[];
  investigative_leads: string[];
};

function CaseWorkspaceContent() {
  const params = useParams();
  const caseId = typeof params?.caseId === "string" ? params.caseId : "";

  const [caseRecord, setCaseRecord] = useState<CaseData | null>(null);
  const [items, setItems] = useState<ItemData[]>([]);
  const [correlation, setCorrelation] = useState<CorrelationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Forms state
  const [noteContent, setNoteContent] = useState("");
  const [noteAuthor, setNoteAuthor] = useState("Investigator");
  const [submittingNote, setSubmittingNote] = useState(false);

  const [attachToken, setAttachToken] = useState("");
  const [attachLabel, setAttachLabel] = useState("");
  const [attachType, setAttachType] = useState("image");
  const [showAttachModal, setShowAttachModal] = useState(false);
  const [attaching, setAttaching] = useState(false);

  const loadCase = async () => {
    if (!caseId) return;
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`${API_BASE_URL}/api/cases/${caseId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setCaseRecord(data.case);
      setItems(data.items || []);
      setCorrelation(data.correlation || null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load case.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCase();
  }, [caseId]);

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!noteContent.trim() || !caseId) return;
    try {
      setSubmittingNote(true);
      const res = await fetch(`${API_BASE_URL}/api/cases/${caseId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          author: noteAuthor.trim() || "Investigator",
          content: noteContent.trim(),
        }),
      });
      if (!res.ok) throw new Error("Failed to add note");
      setNoteContent("");
      await loadCase();
    } catch (err) {
      alert("Error adding note to case.");
    } finally {
      setSubmittingNote(false);
    }
  };

  const handleAttachItem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!attachToken.trim() || !caseId) return;
    try {
      setAttaching(true);
      const res = await fetch(`${API_BASE_URL}/api/cases/${caseId}/attach`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: attachToken.trim(),
          label: attachLabel.trim() || `Evidence #${items.length + 1}`,
          item_type: attachType,
        }),
      });
      if (!res.ok) {
        const errJson = await res.json();
        throw new Error(errJson.detail || "Could not attach item");
      }
      setShowAttachModal(false);
      setAttachToken("");
      setAttachLabel("");
      await loadCase();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Error attaching evidence.");
    } finally {
      setAttaching(false);
    }
  };

  const handleRemoveItem = async (token: string) => {
    if (!confirm(`Remove evidence item '${token}' from this case?`)) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/cases/${caseId}/items/${token}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Could not remove item");
      await loadCase();
    } catch (err) {
      alert("Failed to remove evidence item.");
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/cases/${caseId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!res.ok) throw new Error("Could not update status");
      await loadCase();
    } catch (err) {
      alert("Failed to update case status.");
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen px-4 py-12 text-slate-100 flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-sky-400 border-t-transparent" />
          <p className="text-sm text-slate-400">Loading case workspace: {caseId}…</p>
        </div>
      </main>
    );
  }

  if (error || !caseRecord) {
    return (
      <main className="min-h-screen px-4 py-12 text-slate-100 max-w-4xl mx-auto">
        <div className="rounded-3xl border border-red-800 bg-red-950/40 p-8 text-center space-y-4">
          <h2 className="text-xl font-bold text-red-300">Case Not Found or Inaccessible</h2>
          <p className="text-sm text-slate-300">{error || "Case record could not be loaded."}</p>
          <Link
            href="/cases"
            className="inline-block rounded-xl bg-slate-800 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
          >
            &larr; Back to Investigation Workspace
          </Link>
        </div>
      </main>
    );
  }

  const hasContradictions = correlation && correlation.contradictions.length > 0;
  const isSelectiveManipulation =
    correlation?.divergence_status === "selective_manipulation_suspected";

  return (
    <main className="min-h-screen px-4 py-8 sm:px-6 lg:px-8 text-slate-100">
      <div className="mx-auto max-w-6xl space-y-8">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center justify-between text-xs text-slate-400">
          <Link href="/cases" className="hover:text-white transition flex items-center gap-1 font-medium">
            &larr; All Investigation Cases
          </Link>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sky-400">{caseRecord.case_id}</span>
            <span>&bull;</span>
            <span>Created {new Date(caseRecord.created_at).toLocaleDateString()}</span>
          </div>
        </div>

        {/* Case Header Card */}
        <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6 sm:p-8 shadow-xl">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="font-mono text-xs font-semibold text-sky-400 bg-sky-950 px-2 py-0.5 rounded border border-sky-800">
                  {caseRecord.case_id}
                </span>
                <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-slate-300">
                  {caseRecord.status.replace("_", " ")}
                </span>
                <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-slate-300">
                  Priority: {caseRecord.priority}
                </span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white">{caseRecord.title}</h1>
              <p className="mt-2 text-sm text-slate-300 max-w-3xl leading-relaxed">
                {caseRecord.description || "No case description provided."}
              </p>
              <div className="mt-3 flex items-center gap-4 text-xs text-slate-400">
                <span>Lead Specialist: <strong className="text-slate-200">{caseRecord.investigator}</strong></span>
                {caseRecord.tags?.length > 0 && (
                  <div className="flex gap-1.5">
                    {caseRecord.tags.map((t) => (
                      <span key={t} className="text-sky-400">#{t}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Quick Actions */}
            <div className="flex flex-wrap sm:flex-col gap-2 shrink-0">
              <a
                href={`${API_BASE_URL}/api/cases/${caseRecord.case_id}/report`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center rounded-xl bg-sky-500 px-4 py-2.5 text-xs font-bold text-slate-950 shadow hover:bg-sky-400 transition"
              >
                Download Official Report (HTML/PDF)
              </a>
              <a
                href={`${API_BASE_URL}/api/cases/${caseRecord.case_id}/export.json`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center rounded-xl border border-slate-700 bg-slate-950 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-800 transition"
              >
                Export Case JSON
              </a>
              <div className="flex items-center gap-1 pt-1">
                <span className="text-[11px] text-slate-400">Status:</span>
                <select
                  value={caseRecord.status}
                  onChange={(e) => handleStatusChange(e.target.value)}
                  className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
                >
                  <option value="open">Open</option>
                  <option value="in_review">In Review</option>
                  <option value="concluded">Concluded</option>
                  <option value="archived">Archived</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Forensic Contradiction & Alert Banner */}
        {hasContradictions && (
          <div className="rounded-3xl border border-amber-600/60 bg-amber-950/40 p-6 backdrop-blur-sm space-y-3">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-amber-400 animate-pulse" />
              <h2 className="text-base font-bold text-amber-200 uppercase tracking-wider">
                Cross-Media Forensic Discrepancy Alert
              </h2>
            </div>
            {isSelectiveManipulation && (
              <p className="text-xs font-semibold text-amber-300">
                CRITICAL: Selective Manipulation / Splicing Indicated. Evidence items in this case exhibit opposing
                authenticity markers (some likely AI, others organic).
              </p>
            )}
            <ul className="space-y-2 mt-2">
              {correlation.contradictions.map((c, idx) => (
                <li key={idx} className="text-xs text-amber-100/90 rounded-xl bg-amber-900/30 p-3 border border-amber-800/40">
                  <span className="font-bold text-amber-300">[{c.severity.toUpperCase()}] {c.type}: </span>
                  {c.description}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Evidence Items Section */}
        <div className="rounded-3xl border border-slate-800 bg-slate-900/60 p-6 sm:p-8 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h2 className="text-xl font-bold text-white">Chain of Custody & Attached Media ({items.length})</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Cryptographically registered digital evidence with SHA-256 fingerprints.
              </p>
            </div>
            <button
              onClick={() => setShowAttachModal(true)}
              className="rounded-xl bg-sky-500/20 text-sky-300 border border-sky-400/30 px-3.5 py-2 text-xs font-semibold hover:bg-sky-500/30 transition"
            >
              + Attach Evidence Token
            </button>
          </div>

          {items.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-800 p-8 text-center text-slate-400">
              <p className="text-sm">No evidence items attached to this case yet.</p>
              <p className="text-xs text-slate-500 mt-1">
                Analyze an image or video on the home page, then attach its token here.
              </p>
              <button
                onClick={() => setShowAttachModal(true)}
                className="mt-4 rounded-xl bg-sky-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-sky-400"
              >
                Attach Evidence Token
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {items.map((it) => {
                const verdict = it.result?.verdict || "Analysis Recorded";
                const isAI = verdict === "Likely AI";
                const isNonAI = verdict === "No AI signs found";
                return (
                  <div
                    key={it.id}
                    className="rounded-2xl border border-slate-800 bg-slate-950/70 p-5 space-y-3 flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-sm text-white line-clamp-1">{it.label}</span>
                        <span
                          className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                            isAI
                              ? "bg-red-950 text-red-300 border border-red-800"
                              : isNonAI
                              ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                              : "bg-amber-950 text-amber-300 border border-amber-800"
                          }`}
                        >
                          {verdict}
                        </span>
                      </div>

                      <div className="mt-2 space-y-1 text-xs text-slate-400">
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] uppercase tracking-wider text-slate-500">Type:</span>
                          <span className="font-semibold text-slate-300 uppercase">{it.item_type}</span>
                          <span className="text-slate-600">&bull;</span>
                          <span className="text-[11px] uppercase tracking-wider text-slate-500">Token:</span>
                          <span className="font-mono text-slate-300">{it.token.slice(0, 10)}…</span>
                        </div>

                        {it.sha256 && (
                          <div className="mt-1">
                            <span className="text-[10px] uppercase tracking-wider text-slate-500 block">SHA-256 Fingerprint:</span>
                            <code className="text-[11px] text-sky-300 break-all font-mono select-all">
                              {it.sha256}
                            </code>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="pt-3 border-t border-slate-900 flex items-center justify-between text-xs">
                      <Link
                        href={`/result/${it.token}`}
                        className="text-sky-400 hover:text-sky-300 font-semibold"
                      >
                        Inspect Full Findings &rarr;
                      </Link>
                      <button
                        onClick={() => handleRemoveItem(it.token)}
                        className="text-red-400 hover:text-red-300"
                      >
                        Detach
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Cross-Media Correlation Engine Findings */}
        {correlation && correlation.total_items > 0 && (
          <div className="rounded-3xl border border-slate-800 bg-slate-900/60 p-6 sm:p-8 space-y-6">
            <div>
              <h2 className="text-xl font-bold text-white">Cross-Media Correlation & Timeline Findings</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Automated multi-asset comparison across capture timestamps, camera profiles, and software footprints.
              </p>
            </div>

            {/* Leads */}
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-sky-400">
                Actionable Investigative Leads ({correlation.investigative_leads.length})
              </h3>
              <ul className="space-y-2 text-xs text-slate-300">
                {correlation.investigative_leads.map((lead, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-sky-400 font-bold">&rsaquo;</span>
                    <span>{lead}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Timeline Table */}
            {correlation.timeline.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Evidence Chronology Sequence
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border border-slate-800 rounded-xl overflow-hidden">
                    <thead className="bg-slate-950 text-slate-400 uppercase tracking-wider">
                      <tr>
                        <th className="p-3">Asset</th>
                        <th className="p-3">Capture / Timestamp</th>
                        <th className="p-3">Camera / Profile</th>
                        <th className="p-3">Verdict</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {correlation.timeline.map((entry, idx) => (
                        <tr key={idx} className="hover:bg-slate-800/40">
                          <td className="p-3 font-semibold text-white">{entry.label}</td>
                          <td className="p-3 font-mono text-slate-300">{entry.timestamp}</td>
                          <td className="p-3 text-slate-300">{entry.camera || "Standard / Redacted"}</td>
                          <td className="p-3 font-bold text-sky-400">{entry.verdict}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Investigator Notes Section */}
        <div className="rounded-3xl border border-slate-800 bg-slate-900/60 p-6 sm:p-8 space-y-6">
          <div>
            <h2 className="text-xl font-bold text-white">Investigator Notes & Audit Log ({caseRecord.notes?.length || 0})</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Append timestamped observations, interview notes, and forensic hypotheses.
            </p>
          </div>

          <div className="space-y-3">
            {caseRecord.notes?.map((n) => (
              <div key={n.id} className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 space-y-1">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span className="font-semibold text-sky-400">{n.author}</span>
                  <span className="font-mono text-[11px]">{new Date(n.timestamp).toLocaleString()}</span>
                </div>
                <p className="text-sm text-slate-200 whitespace-pre-wrap leading-relaxed">{n.content}</p>
              </div>
            ))}
          </div>

          <form onSubmit={handleAddNote} className="space-y-3 pt-4 border-t border-slate-800">
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
              <div className="sm:col-span-1">
                <input
                  type="text"
                  placeholder="Author"
                  value={noteAuthor}
                  onChange={(e) => setNoteAuthor(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-sky-400 focus:outline-none"
                />
              </div>
              <div className="sm:col-span-3">
                <textarea
                  rows={2}
                  required
                  placeholder="Add note, verification observation, or lead hypothesis…"
                  value={noteContent}
                  onChange={(e) => setNoteContent(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:border-sky-400 focus:outline-none"
                />
              </div>
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={submittingNote}
                className="rounded-xl bg-sky-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-sky-400 disabled:opacity-60 transition"
              >
                {submittingNote ? "Recording…" : "Add Note to Audit Trail"}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Attach Item Modal */}
      {showAttachModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-2xl">
            <h2 className="text-lg font-bold text-white">Attach Evidence to Case</h2>
            <p className="mt-1 text-xs text-slate-400">
              Provide the analysis token from a previously completed image or video check.
            </p>

            <form onSubmit={handleAttachItem} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Result Token *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 16-character token from /result/{token}"
                  value={attachToken}
                  onChange={(e) => setAttachToken(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs font-mono text-slate-100 placeholder-slate-500 focus:border-sky-400 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Evidence Label
                </label>
                <input
                  type="text"
                  placeholder="e.g. Disputed Tweet Image 1"
                  value={attachLabel}
                  onChange={(e) => setAttachLabel(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:border-sky-400 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Media Type
                </label>
                <select
                  value={attachType}
                  onChange={(e) => setAttachType(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100 focus:border-sky-400 focus:outline-none"
                >
                  <option value="image">Image</option>
                  <option value="video">Video</option>
                </select>
              </div>

              <div className="mt-6 flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAttachModal(false)}
                  className="rounded-xl px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={attaching}
                  className="rounded-xl bg-sky-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-sky-400 disabled:opacity-60"
                >
                  {attaching ? "Attaching…" : "Attach Evidence"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}

export default function CaseWorkspacePage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen px-4 py-8 text-slate-100 sm:px-6 sm:py-12">
          <div className="mx-auto max-w-6xl p-8 text-slate-300">
            Loading investigation case workspace…
          </div>
        </main>
      }
    >
      <CaseWorkspaceContent />
    </Suspense>
  );
}

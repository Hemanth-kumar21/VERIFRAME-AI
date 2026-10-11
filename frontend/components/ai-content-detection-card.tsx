"use client";

import { useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function toList(val: unknown): string[] {
  if (Array.isArray(val)) return val.map((x) => String(x).trim()).filter(Boolean);
  if (typeof val === "string" && val.trim()) return [val.trim()];
  return [];
}

export type AiContentDetectionData = {
  ai_probability: number | null;
  human_probability: number | null;
  classification: "Likely AI-Generated" | "Likely Human-Created" | "Inconclusive" | string;
  confidence: "Low" | "Medium" | "High" | string;
  is_calibrated: boolean;
  score_label: string;
  evidence: string[];
  analyzed_frames: number;
  scored_frames: number;
  model_info?: {
    models: string[];
    method: string;
    limitations: string[];
  };
  status: string;
};

interface AiContentDetectionCardProps {
  detection?: AiContentDetectionData | null;
  token: string;
  mediaType: "video" | "image";
  fallbackVerdict?: string;
  fallbackStrength?: string;
}

export default function AiContentDetectionCard({
  detection,
  token,
  mediaType,
  fallbackVerdict = "Inconclusive",
  fallbackStrength = "Moderate",
}: AiContentDetectionCardProps) {
  const [showDetails, setShowDetails] = useState(true);
  const [showModels, setShowModels] = useState(false);

  // Derive values with robust fallbacks
  const classification =
    detection?.classification ??
    (fallbackVerdict === "Likely AI"
      ? "Likely AI-Generated"
      : fallbackVerdict === "No AI signs found"
      ? "Likely Human-Created"
      : "Inconclusive");

  const confidence = detection?.confidence ?? (fallbackStrength === "Strong" ? "High" : fallbackStrength === "Moderate" ? "Medium" : "Low");
  const aiProb = detection?.ai_probability;
  const humanProb = detection?.human_probability;
  const hasProbabilities = aiProb !== null && aiProb !== undefined && humanProb !== null && humanProb !== undefined;
  const analyzedFrames = detection?.analyzed_frames ?? (mediaType === "video" ? 6 : 1);
  const scoredFrames = detection?.scored_frames ?? (hasProbabilities ? analyzedFrames : 0);
  const evidenceList = detection?.evidence ?? [
    "Consensus detector evaluation completed across sampled representations.",
  ];
  const modelInfo = detection?.model_info;
  const scoreLabel = detection?.score_label ?? (detection?.is_calibrated ? "Calibrated Probability" : "AI-Likelihood Score");

  // Style classes based on classification
  const classificationBadge =
    classification === "Likely AI-Generated"
      ? "bg-rose-500/20 text-rose-300 border-rose-500/40"
      : classification === "Likely Human-Created"
      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
      : "bg-amber-500/20 text-amber-300 border-amber-500/40";

  const confidenceBadge =
    confidence === "High"
      ? "bg-sky-500/20 text-sky-300 border-sky-500/40"
      : confidence === "Medium"
      ? "bg-indigo-500/20 text-indigo-300 border-indigo-500/40"
      : "bg-slate-700/50 text-slate-300 border-slate-600";

  return (
    <section
      aria-labelledby="ai-content-detection-heading"
      className="rounded-3xl border border-sky-400/30 bg-gradient-to-br from-slate-950 via-slate-900/95 to-slate-950 p-6 sm:p-7 shadow-xl space-y-6"
    >
      {/* Header with Title & Classification Badges */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-2.5 w-2.5 rounded-full bg-sky-400 animate-pulse" />
            <h2
              id="ai-content-detection-heading"
              className="text-xl sm:text-2xl font-bold text-white tracking-tight"
            >
              AI Content Detection Results
            </h2>
          </div>
          <p className="mt-1 text-xs sm:text-sm text-slate-300">
            {mediaType === "video"
              ? "Multi-frame temporal consistency & authenticity analysis"
              : "Single-image spatial frequency & deep neural artifact analysis"}
          </p>
        </div>

        {/* Classification & Confidence Badges */}
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center px-3 py-1 rounded-xl text-xs font-semibold border shadow-sm ${classificationBadge}`}
          >
            {classification}
          </span>
          <span
            className={`inline-flex items-center px-2.5 py-1 rounded-xl text-xs font-medium border ${confidenceBadge}`}
          >
            {confidence} Confidence
          </span>
          <span className="inline-flex items-center px-2.5 py-1 rounded-xl text-xs font-medium bg-slate-800/80 border border-slate-700 text-slate-300">
            {analyzedFrames} Frame{analyzedFrames > 1 ? "s" : ""} Analyzed
          </span>
        </div>
      </div>

      {/* Probability Display and Visual Gauge */}
      {hasProbabilities ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-5 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* AI Generated Probability */}
            <div className="rounded-xl border border-rose-500/20 bg-rose-950/20 p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase tracking-wider font-semibold text-rose-300">
                  AI-Generated Probability
                </span>
                <span className="text-[11px] text-rose-400/80 font-mono">({scoreLabel})</span>
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl sm:text-4xl font-extrabold text-rose-200 tracking-tight">
                  {aiProb?.toFixed(1)}%
                </span>
                <span className="text-xs text-rose-400">likelihood</span>
              </div>
            </div>

            {/* Likely Human-Created Probability */}
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/20 p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase tracking-wider font-semibold text-emerald-300">
                  Likely Human-Created Probability
                </span>
                <span className="text-[11px] text-emerald-400/80 font-mono">(Authenticity)</span>
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl sm:text-4xl font-extrabold text-emerald-200 tracking-tight">
                  {humanProb?.toFixed(1)}%
                </span>
                <span className="text-xs text-emerald-400">complement</span>
              </div>
            </div>
          </div>

          {/* Visual Dual Progress Bar / Split Gauge */}
          <div className="space-y-1.5 pt-1">
            <div className="flex justify-between text-[11px] text-slate-400 font-mono">
              <span className="text-rose-400 font-semibold">AI: {aiProb?.toFixed(1)}%</span>
              <span className="text-emerald-400 font-semibold">Human: {humanProb?.toFixed(1)}%</span>
            </div>
            <div className="h-4 w-full rounded-full bg-slate-900 border border-slate-700/80 overflow-hidden flex">
              <div
                style={{ width: `${Math.min(100, Math.max(0, aiProb ?? 0))}%` }}
                className="bg-gradient-to-r from-rose-600 via-rose-500 to-amber-500 transition-all duration-700 ease-out"
                role="progressbar"
                aria-valuenow={aiProb ?? 0}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="AI-Generated Probability"
              />
              <div
                style={{ width: `${Math.min(100, Math.max(0, humanProb ?? 0))}%` }}
                className="bg-gradient-to-r from-emerald-600 to-teal-400 transition-all duration-700 ease-out"
                role="progressbar"
                aria-valuenow={humanProb ?? 0}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Likely Human-Created Probability"
              />
            </div>
            <div className="flex justify-between text-[10px] text-slate-500 px-1 pt-0.5">
              <span>0% (Natural baseline)</span>
              <span>Threshold: 65%</span>
              <span>100% (Synthetic)</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-950/20 p-5 space-y-2">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-amber-300">
            Probability Inconclusive
          </h3>
          <p className="text-sm text-slate-300 leading-relaxed">
            The configured detection models did not produce definitive calibrated probability scores for this media item. The analysis concluded with an <strong>Inconclusive</strong> status rather than generating an ungrounded or speculative percentage.
          </p>
        </div>
      )}

      {/* Evidence and Explanation Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-sky-300 flex items-center gap-2">
            <span>🔍</span> Evidence & Diagnostic Explanation
          </h3>
          <button
            type="button"
            onClick={() => setShowDetails((prev) => !prev)}
            className="text-xs text-sky-400 hover:text-sky-300 underline font-medium"
          >
            {showDetails ? "Hide details" : "Show all evidence"}
          </button>
        </div>

        {showDetails && (
          <ul className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 space-y-2.5 text-sm text-slate-300 leading-relaxed list-disc pl-7">
            {evidenceList.map((item, idx) => (
              <li key={`ev-${idx}`} className="marker:text-sky-400">
                {item}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Model Information Drawer (Expandable) */}
      {modelInfo && (
        <div className="rounded-2xl border border-slate-800/80 bg-slate-950/40 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-mono">
              Methodology & Model Architecture
            </span>
            <button
              type="button"
              onClick={() => setShowModels((prev) => !prev)}
              className="text-xs text-slate-400 hover:text-slate-200 underline"
            >
              {showModels ? "Collapse model info" : "View model details"}
            </button>
          </div>

          {showModels && (
            <div className="mt-3 space-y-3 text-xs text-slate-300 border-t border-slate-800/80 pt-3">
              <div>
                <span className="font-semibold text-slate-200">Active Models: </span>
                <span className="font-mono text-sky-300">{toList(modelInfo.models).join(", ") || "Configured classifiers"}</span>
              </div>
              <div>
                <span className="font-semibold text-slate-200">Aggregation Method: </span>
                <span>{modelInfo.method}</span>
              </div>
              {toList(modelInfo.limitations).length > 0 && (
                <div>
                  <span className="font-semibold text-slate-200 block mb-1">Documented Limitations:</span>
                  <ul className="list-disc pl-4 space-y-1 text-slate-400">
                    {toList(modelInfo.limitations).map((lim, lIdx) => (
                      <li key={lIdx}>{lim}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Downloadable Report Action Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 pt-5">
        <p className="text-xs text-slate-400 italic">
          * AI-generated content detection is probabilistic and represents an empirical assessment, not absolute proof.
        </p>

        <div className="flex flex-wrap items-center gap-2">
          {/* Download Forensic Dossier (HTML / Printable PDF) */}
          <a
            href={`${API_BASE_URL}/api/result/${encodeURIComponent(token)}/dossier`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-xl bg-sky-500 px-3.5 py-2 text-xs font-semibold text-slate-950 hover:bg-sky-400 transition shadow-sm"
          >
            <span>📄</span>
            <span>Download Dossier (PDF/HTML)</span>
          </a>

          {/* Download Raw JSON Evidence */}
          <a
            href={`${API_BASE_URL}/api/result/${encodeURIComponent(token)}/export.json`}
            download={`evidence-${token}.json`}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-medium text-slate-300 hover:border-slate-500 hover:text-white transition"
          >
            <span>💾</span>
            <span>Export JSON Record</span>
          </a>
        </div>
      </div>
    </section>
  );
}

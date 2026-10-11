"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { getVideoPreview, releaseVideoPreview } from "@/lib/video-preview-store";
import AiContentDetectionCard, { AiContentDetectionData } from "./ai-content-detection-card";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function toList(val: unknown): string[] {
  if (Array.isArray(val)) return val.map((x) => String(x).trim()).filter(Boolean);
  if (typeof val === "string" && val.trim()) return [val.trim()];
  return [];
}

type VideoFrameEvidence = {
  timestamp: number;
  frame_index: number;
  scene_id: number;
  quality: { usable: boolean; limitations: string[] };
  signal: string;
  agreement: string;
  mean_score: number | null;
  status: string;
};

type VideoSummary = {
  verdict: string;
  evidence_strength: string;
  agreement: string;
  analyzed_frame_count: number;
  scored_frame_count: number;
  suspicious_signal_count: number;
  scene_coverage_count: number;
  frames: VideoFrameEvidence[];
  video_info: {
    duration_seconds: number;
    width: number;
    height: number;
    fps: number;
    video_codec: string;
    container: string;
    has_audio: boolean;
    audio_codec: string | null;
    audio_authenticity_assessed: boolean;
  };
  temporal_checks: {
    status: string;
    unstable_neighbor_pairs: Array<{
      start_timestamp: number;
      end_timestamp: number;
      score_delta: number;
    }>;
    note: string;
  };
  face_tracking: { status: string; message: string };
  what_was_not_checked: string[];
  limitations: string[];
  scene_detection_status: string;
  scene_changes: number[];
};

type NemotronEvent = {
  timestamp_seconds?: number;
  timestamp_formatted?: string;
  description: string;
  visible_objects?: string[];
  actions?: string[];
  confidence?: string;
};

type NemotronScene = {
  scene_id?: number;
  start_time?: string;
  description: string;
};

type NemotronAnalysis = {
  status: string;
  model?: string;
  sampled_frames_used?: number;
  summary?: string;
  scene_descriptions?: NemotronScene[];
  timestamped_events?: NemotronEvent[];
  important_observations?: string[] | string;
  limitations?: string[] | string;
  message?: string;
  error?: string;
};

type VideoResult = {
  verdict: string;
  evidence_strength: string;
  agreement: string;
  explanation: Record<string, string>;
  tool_summaries: {
    video: VideoSummary;
    nemotron?: NemotronAnalysis;
    integrity?: Record<string, unknown>;
    ai_content_detection?: AiContentDetectionData;
  };
  nemotron?: NemotronAnalysis;
  ai_content_detection?: AiContentDetectionData;
};

type QAMessage = {
  id: string;
  question: string;
  answer: string;
  model?: string;
  timestamp: string;
};

const COPY = {
  en: {
    title: "Video authenticity & intelligence investigation",
    preview: "Video preview",
    unavailable: "The original video is not retained by the server. Preview it again from the upload page; analysis results do not contain uploaded media.",
    info: "Video information",
    duration: "Duration",
    frames: "Sampled frames",
    suspicious: "Suspicious signals",
    audio: "Audio",
    audioNotAssessed: "Audio authenticity was not assessed.",
    timeline: "Evidence timeline",
    signalNotice: "Evidence signal — not proof of manipulation.",
    frame: "Frame",
    noSignals: "No suspicious signal was returned for this sampled frame.",
    temporal: "Temporal checks",
    faces: "Face tracking",
    notChecked: "What was not checked",
    limitations: "Limitations",
    share: "Share result",
    copied: "Result link copied.",
    copyFailed: "Unable to share or copy this result link.",
    back: "Back to upload",
    loading: "Loading video investigation…",
    nemotronTitle: "NVIDIA Nemotron Video Intelligence",
    nemotronSubtitle: "Multimodal AI video comprehension powered by NVIDIA Nemotron-3-Nano-Omni",
    nemotronSummary: "Narrative Video Summary",
    nemotronEvents: "Timestamped Action & Event Timeline",
    nemotronObservations: "Important Visual Observations",
    nemotronLimitations: "Sampling & Model Limitations",
    nemotronApproxTs: "Approx.",
    nemotronClickToSeek: "Click timestamp to seek video",
    nemotronAskTitle: "Ask Nemotron About This Video",
    nemotronAskSubtitle: "Ask natural-language questions grounded strictly in the sampled visual evidence",
    nemotronPlaceholder: "e.g., What actions occur in this clip? What changes from beginning to end?",
    nemotronAskBtn: "Ask Nemotron",
    nemotronAsking: "Reasoning…",
    nemotronGroundedNotice: "Answers are grounded strictly in sampled visual frames. The model will disclose when evidence is insufficient.",
    nemotronQuickPrompts: [
      "What is happening throughout this video?",
      "What actions does the subject perform?",
      "What changes between the beginning and end?",
      "Summarize the video in 5 bullet points.",
      "Describe any notable scene transitions.",
    ],
  },
  te: {
    title: "వీడియో ప్రామాణికత & విశ్లేషణ పరిశీలన",
    preview: "వీడియో ప్రివ్యూ",
    unavailable: "సర్వర్ అసలు వీడియోను నిల్వ చేయదు. అప్‌లోడ్ పేజీ నుండి మళ్లీ ప్రివ్యూ చేయండి.",
    info: "వీడియో సమాచారం",
    duration: "నిడివి",
    frames: "నమూనా ఫ్రేమ్‌లు",
    suspicious: "అనుమాన సూచనలు",
    audio: "ఆడియో",
    audioNotAssessed: "ఆడియో ప్రామాణికతను పరిశీలించలేదు.",
    timeline: "ఆధారాల కాలక్రమం",
    signalNotice: "ఆధార సూచన — మార్పుకు రుజువు కాదు.",
    frame: "ఫ్రేమ్",
    noSignals: "ఈ నమూనా ఫ్రేమ్‌కు అనుమాన సూచన లేదు.",
    temporal: "కాలక్రమ తనిఖీలు",
    faces: "ముఖాల ట్రాకింగ్",
    notChecked: "పరిశీలించనివి",
    limitations: "పరిమితులు",
    share: "ఫలితాన్ని పంచుకోండి",
    copied: "ఫలిత లింక్ కాపీ అయింది.",
    copyFailed: "ఫలిత లింక్‌ను పంచడం లేదా కాపీ చేయడం సాధ్యం కాలేదు.",
    back: "అప్‌లోడ్‌కు తిరిగి వెళ్ళండి",
    loading: "వీడియో పరిశీలన లోడ్ అవుతోంది…",
    nemotronTitle: "NVIDIA Nemotron వీడియో విశ్లేషణ",
    nemotronSubtitle: "NVIDIA Nemotron-3-Nano-Omni మల్టీమోడల్ విశ్లేషణ",
    nemotronSummary: "సారాంశ వివరణ",
    nemotronEvents: "కాలక్రమ చర్యలు మరియు సంఘటనలు",
    nemotronObservations: "ముఖ్య పరిశీలనలు",
    nemotronLimitations: "పరిమితులు",
    nemotronApproxTs: "సుమారు",
    nemotronClickToSeek: "వీడియోలో ఈ సమయానికి వెళ్లండి",
    nemotronAskTitle: "ఈ వీడియో గురించి ప్రశ్నలు అడగండి",
    nemotronAskSubtitle: "వీడియోలోని దృశ్య ఆధారాల ఆధారంగా సమాధానాలు పొందండి",
    nemotronPlaceholder: "ఉదా: ఈ వీడియోలో ఏమి జరుగుతోంది?",
    nemotronAskBtn: "ప్రశ్నించండి",
    nemotronAsking: "ఆలోచిస్తోంది…",
    nemotronGroundedNotice: "సమాధానాలు సేకరించిన దృశ్య ఆధారాలపై ఆధారపడి ఉంటాయి.",
    nemotronQuickPrompts: [
      "ఈ వీడియోలో ఏమి జరుగుతోంది?",
      "వ్యక్తి ఏ పనులు చేస్తున్నాడు?",
      "మొదటికీ చివరికీ ఏమి మార్పులు వచ్చాయి?",
      "5 పాయింట్లలో సారాంశం ఇవ్వండి.",
    ],
  },
  hi: {
    title: "वीडियो प्रामाणिकता एवं बुद्धिमत्ता जाँच",
    preview: "वीडियो पूर्वावलोकन",
    unavailable: "सर्वर मूल वीडियो को सहेजता नहीं है। अपलोड पेज से फिर से पूर्वावलोकन करें।",
    info: "वीडियो जानकारी",
    duration: "अवधि",
    frames: "नमूना फ़्रेम",
    suspicious: "संदिग्ध संकेत",
    audio: "ऑडियो",
    audioNotAssessed: "ऑडियो की प्रामाणिकता का आकलन नहीं किया गया।",
    timeline: "साक्ष्य समयरेखा",
    signalNotice: "साक्ष्य संकेत — हेरफेर का प्रमाण नहीं।",
    frame: "फ़्रेम",
    noSignals: "इस नमूना फ़्रेम से कोई संदिग्ध संकेत नहीं मिला।",
    temporal: "कालानुक्रमिक जाँच",
    faces: "चेहरा ट्रैकिंग",
    notChecked: "जिनकी जाँच नहीं हुई",
    limitations: "सीमाएँ",
    share: "परिणाम साझा करें",
    copied: "परिणाम लिंक कॉपी किया गया।",
    copyFailed: "परिणाम लिंक साझा या कॉपी नहीं किया जा सका।",
    back: "अपलोड पर वापस जाएँ",
    loading: "वीडियो जाँच लोड हो रही है…",
    nemotronTitle: "NVIDIA Nemotron वीडियो बुद्धिमत्ता",
    nemotronSubtitle: "NVIDIA Nemotron-3-Nano-Omni द्वारा संचालित मल्टीमॉडल वीडियो विश्लेषण",
    nemotronSummary: "विस्तृत वीडियो सारांश",
    nemotronEvents: "समयबद्ध क्रियाएं और घटनाएं",
    nemotronObservations: "महत्वपूर्ण अवलोकन",
    nemotronLimitations: "नमूनाकरण और मॉडल सीमाएँ",
    nemotronApproxTs: "लगभग",
    nemotronClickToSeek: "वीडियो में इस समय पर जाएँ",
    nemotronAskTitle: "वीडियो के बारे में प्रश्न पूछें",
    nemotronAskSubtitle: "केवल एकत्रित दृश्य साक्ष्यों पर आधारित प्रश्नोत्तर",
    nemotronPlaceholder: "जैसे: इस वीडियो में क्या हो रहा है?",
    nemotronAskBtn: "पूछें",
    nemotronAsking: "विश्लेषण जारी…",
    nemotronGroundedNotice: "उत्तर केवल एकत्रित वीडियो फ़्रेमों के साक्ष्यों पर आधारित हैं।",
    nemotronQuickPrompts: [
      "इस वीडियो में क्या हो रहा है?",
      "व्यक्ति क्या क्रियाएं कर रहा है?",
      "शुरुआत और अंत में क्या परिवर्तन आया?",
      "5 बिंदुओं में सारांश दें।",
    ],
  },
} as const;

function formatTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainder = (seconds % 60).toFixed(1).padStart(4, "0");
  return `${String(minutes).padStart(2, "0")}:${remainder}`;
}

export default function VideoResultView({ token }: { token: string }) {
  const [result, setResult] = useState<VideoResult | null>(null);
  const [error, setError] = useState("");
  const [language, setLanguage] = useState<keyof typeof COPY>("en");
  const [notice, setNotice] = useState("");
  const [qaInput, setQaInput] = useState("");
  const [qaLoading, setQaLoading] = useState(false);
  const [qaError, setQaError] = useState("");
  const [qaHistory, setQaHistory] = useState<QAMessage[]>([]);
  const videoRef = useRef<HTMLVideoElement>(null);
  const previewMessageRef = useRef<HTMLParagraphElement>(null);
  const text = COPY[language];

  useEffect(() => {
    const controller = new AbortController();
    void fetch(`${API_BASE_URL}/api/video/result/${encodeURIComponent(token)}`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("This video result could not be found.");
        const payload = (await response.json()) as VideoResult;
        if (
          typeof payload.verdict !== "string" ||
          !payload.tool_summaries ||
          !payload.tool_summaries.video
        ) {
          throw new Error("The backend returned an invalid video result.");
        }
        setResult(payload);
      })
      .catch((loadError: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            loadError instanceof Error ? loadError.message : "The video result is unavailable.",
          );
        }
      });
    return () => {
      controller.abort();
    };
  }, [token]);

  useEffect(() => {
    if (!result || !videoRef.current) return;
    const retainedPreview = getVideoPreview(token);
    if (!retainedPreview) return;
    videoRef.current.src = retainedPreview;
    videoRef.current.dataset.localPreview = "true";
    videoRef.current.hidden = false;
    if (previewMessageRef.current) previewMessageRef.current.hidden = true;
  }, [result, token]);

  const seekTo = (timestamp: number) => {
    if (!videoRef.current || videoRef.current.dataset.localPreview !== "true") {
      setNotice(text.unavailable);
      return;
    }
    videoRef.current.currentTime = Math.max(0, timestamp);
    videoRef.current.pause();
    videoRef.current.focus();
    setNotice(`Jumped preview player to ${formatTime(timestamp)}.`);
  };

  const shareResult = async () => {
    const url = window.location.href;
    try {
      if (navigator.share) {
        await navigator.share({ title: "Very Frame AI video result", url });
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(url);
        setNotice(text.copied);
      } else {
        throw new Error("No share API is available.");
      }
    } catch (shareError) {
      if (shareError instanceof Error && shareError.name === "AbortError") return;
      setNotice(text.copyFailed);
    }
  };

  const handleAskQuestion = async (customPrompt?: string) => {
    const questionText = (customPrompt ?? qaInput).trim();
    if (!questionText || qaLoading) return;

    setQaLoading(true);
    setQaError("");
    try {
      const response = await fetch(`${API_BASE_URL}/api/video/${encodeURIComponent(token)}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: questionText }),
      });

      const data = (await response.json().catch(() => null)) as {
        answer?: string;
        model?: string;
        detail?: string;
      } | null;

      if (!response.ok) {
        throw new Error(data?.detail ?? "Failed to get an answer from NVIDIA Nemotron.");
      }

      const answer = data?.answer ?? "No response generated.";
      const newEntry: QAMessage = {
        id: Math.random().toString(36).substring(2, 9),
        question: questionText,
        answer,
        model: data?.model ?? "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setQaHistory((prev) => [...prev, newEntry]);
      if (!customPrompt) setQaInput("");
    } catch (askErr) {
      setQaError(askErr instanceof Error ? askErr.message : "Error contacting NVIDIA Nemotron.");
    } finally {
      setQaLoading(false);
    }
  };

  if (error) {
    return (
      <main className="min-h-screen px-4 py-10 text-slate-100 sm:px-6">
        <section
          role="alert"
          className="mx-auto max-w-3xl rounded-2xl border border-amber-400/30 bg-amber-500/10 p-6 text-amber-100"
        >
          {error}
          <p className="mt-4">
            <Link className="underline" href="/">
              {text.back}
            </Link>
          </p>
        </section>
      </main>
    );
  }
  if (!result) {
    return <p role="status" className="mx-auto max-w-4xl p-8 text-slate-300">{text.loading}</p>;
  }

  const video = result.tool_summaries.video;
  const nemotron = result.tool_summaries.nemotron ?? result.nemotron;
  const localizedExplanation = result.explanation[language] ?? result.explanation.en;
  const warningClass =
    result.verdict === "Likely AI"
      ? "border-amber-400/40 bg-amber-500/10 text-amber-100"
      : "border-sky-400/30 bg-slate-900/70 text-slate-100";

  return (
    <main className="min-h-screen px-4 py-8 text-slate-100 sm:px-6 sm:py-12">
      <div className="mx-auto max-w-5xl space-y-6">
        {/* Header */}
        <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 rounded-3xl border border-sky-400/20 bg-slate-950/50 p-6 sm:p-8">
          <div>
            <div className="flex items-center gap-2">
              <p className="text-xs uppercase tracking-[0.3em] text-sky-300">Very Frame AI</p>
              <span className="inline-flex items-center rounded-full bg-emerald-500/20 px-2 py-0.5 text-[11px] font-semibold text-emerald-300 border border-emerald-500/40">
                NVIDIA Nemotron Integrated
              </span>
            </div>
            <h1 className="mt-2 text-2xl sm:text-3xl font-semibold text-white">{text.title}</h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <a
              href={`${API_BASE_URL}/api/result/${encodeURIComponent(token)}/dossier`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center rounded-xl bg-sky-500 px-3.5 py-2 text-xs font-semibold text-slate-950 hover:bg-sky-400 transition shadow-sm"
            >
              Forensic Dossier (HTML/PDF)
            </a>
            <Link
              href="/cases"
              className="inline-flex items-center rounded-xl border border-sky-800/60 bg-sky-950/40 px-3 py-2 text-xs font-medium text-sky-300 hover:bg-sky-900/40 transition"
            >
              Attach to Case
            </Link>
          </div>
        </header>

        {/* Video Preview & Primary Verdict */}
        <section className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="overflow-hidden rounded-2xl border border-slate-700 bg-slate-950 p-3">
            <h2 className="mb-3 text-lg font-semibold">{text.preview}</h2>
            <video
              ref={videoRef}
              controls
              playsInline
              preload="metadata"
              aria-label={text.preview}
              hidden
              className="max-h-[28rem] w-full rounded-xl bg-black object-contain"
            />
            <p ref={previewMessageRef} className="rounded-xl bg-slate-900 p-4 text-sm leading-6 text-slate-300">
              {text.unavailable}
            </p>
          </div>
          <div className="space-y-4">
            <section className={`rounded-2xl border p-5 ${warningClass}`}>
              <p className="text-sm uppercase tracking-wider">Verdict · {result.evidence_strength} evidence</p>
              <h2 className="mt-2 text-2xl font-semibold">{result.verdict}</h2>
              <p className="mt-3 leading-6">{localizedExplanation}</p>
              <p className="mt-3 text-xs">{text.signalNotice}</p>
            </section>
            <div className="flex flex-wrap gap-2">
              {(["en", "te", "hi"] as const).map((code) => (
                <button
                  key={code}
                  type="button"
                  aria-pressed={language === code}
                  onClick={() => setLanguage(code)}
                  className="min-h-11 rounded-lg border border-slate-700 px-4 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-300 transition hover:border-slate-500"
                >
                  {code.toUpperCase()}
                </button>
              ))}
              <button
                type="button"
                onClick={() => void shareResult()}
                className="min-h-11 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-sky-400 transition"
              >
                {text.share}
              </button>
            </div>
          </div>
        </section>

        {/* ================================================================= */}
        {/* AI-GENERATED CONTENT DETECTION & AUTHENTICITY SCORE SECTION       */}
        {/* ================================================================= */}
        <AiContentDetectionCard
          detection={result.ai_content_detection ?? result.tool_summaries.ai_content_detection}
          token={token}
          mediaType="video"
          fallbackVerdict={result.verdict}
          fallbackStrength={result.evidence_strength}
        />

        {/* ================================================================= */}
        {/* NVIDIA NEMOTRON VIDEO INTELLIGENCE & EVENT TIMELINE SECTION       */}
        {/* ================================================================= */}
        <section className="rounded-3xl border border-emerald-500/30 bg-gradient-to-br from-slate-950 via-slate-900/90 to-emerald-950/20 p-6 sm:p-8 shadow-xl space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-emerald-500/20 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse" />
                <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                  {text.nemotronTitle}
                </h2>
              </div>
              <p className="mt-1 text-sm text-slate-300">{text.nemotronSubtitle}</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="rounded-lg bg-emerald-950/80 border border-emerald-500/40 px-3 py-1 text-xs font-mono text-emerald-300">
                nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
              </span>
              {nemotron?.sampled_frames_used ? (
                <span className="rounded-lg bg-slate-800/80 border border-slate-700 px-2.5 py-1 text-xs text-slate-300">
                  {nemotron.sampled_frames_used} sampled frames
                </span>
              ) : null}
            </div>
          </div>

          {nemotron && nemotron.status === "completed" ? (
            <div className="space-y-6">
              {/* Narrative Summary */}
              {nemotron.summary && (
                <div className="rounded-2xl border border-emerald-500/20 bg-slate-950/70 p-5 backdrop-blur-sm">
                  <h3 className="text-sm font-semibold uppercase tracking-wider text-emerald-400">
                    {text.nemotronSummary}
                  </h3>
                  <p className="mt-3 text-base leading-relaxed text-slate-100 font-sans">
                    {nemotron.summary}
                  </p>
                </div>
              )}

              {/* Timestamped Action & Event Timeline */}
              {nemotron.timestamped_events && nemotron.timestamped_events.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-base font-semibold text-white">
                      {text.nemotronEvents}
                    </h3>
                    <span className="text-xs text-slate-400">
                      {text.nemotronClickToSeek}
                    </span>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {nemotron.timestamped_events.map((evt, idx) => {
                      const tsSec = evt.timestamp_seconds ?? idx * 2.0;
                      const formatted = evt.timestamp_formatted ?? formatTime(tsSec);
                      const confidenceColor =
                        evt.confidence === "high"
                          ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                          : evt.confidence === "tentative"
                          ? "bg-amber-500/20 text-amber-300 border-amber-500/30"
                          : "bg-sky-500/20 text-sky-300 border-sky-500/30";

                      return (
                        <div
                          key={`nem-evt-${idx}`}
                          className="flex flex-col justify-between rounded-xl border border-slate-800 bg-slate-950/80 p-4 hover:border-emerald-500/50 transition"
                        >
                          <div>
                            <div className="flex items-center justify-between gap-2 mb-2">
                              <button
                                type="button"
                                onClick={() => seekTo(tsSec)}
                                className="group inline-flex items-center gap-1.5 rounded-lg bg-emerald-950/70 hover:bg-emerald-900 border border-emerald-500/40 px-2.5 py-1 text-xs font-mono text-emerald-300 transition"
                                title={text.nemotronClickToSeek}
                              >
                                <span>▶</span>
                                <span className="font-semibold">
                                  {text.nemotronApproxTs} {formatted}
                                </span>
                              </button>
                              {evt.confidence && (
                                <span
                                  className={`rounded-md border px-2 py-0.5 text-[11px] font-medium capitalize ${confidenceColor}`}
                                >
                                  {evt.confidence}
                                </span>
                              )}
                            </div>
                            <p className="text-sm font-medium leading-snug text-slate-200">
                              {evt.description}
                            </p>
                          </div>

                          <div className="mt-3 flex flex-wrap gap-1.5 pt-2 border-t border-slate-900">
                            {evt.actions?.map((act, actIdx) => (
                              <span
                                key={actIdx}
                                className="rounded bg-sky-950/80 border border-sky-800/50 px-2 py-0.5 text-[11px] text-sky-300"
                              >
                                {act}
                              </span>
                            ))}
                            {evt.visible_objects?.map((obj, objIdx) => (
                              <span
                                key={objIdx}
                                className="rounded bg-slate-800/80 border border-slate-700 px-2 py-0.5 text-[11px] text-slate-300"
                              >
                                {obj}
                              </span>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <p className="text-xs text-slate-400 italic">
                    * Timestamps are estimated based on frame sampling intervals and scene transitions.
                  </p>
                </div>
              )}

              {/* Observations & Model Limitations Grid */}
              <div className="grid gap-4 sm:grid-cols-2">
                {toList(nemotron.important_observations).length > 0 && (
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-5">
                    <h4 className="text-sm font-semibold uppercase tracking-wider text-sky-300">
                      {text.nemotronObservations}
                    </h4>
                    <ul className="mt-3 space-y-2 list-disc pl-5 text-sm text-slate-300 leading-relaxed">
                      {toList(nemotron.important_observations).map((obs, idx) => (
                        <li key={idx}>{obs}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {toList(nemotron.limitations).length > 0 && (
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-5">
                    <h4 className="text-sm font-semibold uppercase tracking-wider text-amber-300">
                      {text.nemotronLimitations}
                    </h4>
                    <ul className="mt-3 space-y-2 list-disc pl-5 text-sm text-slate-300 leading-relaxed">
                      {toList(nemotron.limitations).map((lim, idx) => (
                        <li key={idx}>{lim}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-6 text-center space-y-3">
              <p className="text-sm text-slate-300">
                {nemotron?.message ||
                  nemotron?.error ||
                  "NVIDIA Nemotron video reasoning is ready. Set your NVIDIA_API_KEY in .env to unlock frame understanding."}
              </p>
            </div>
          )}

          {/* =============================================================== */}
          {/* INTERACTIVE VIDEO QUESTION-ANSWERING ASSISTANT                 */}
          {/* =============================================================== */}
          <div className="mt-6 border-t border-emerald-500/20 pt-6 space-y-4">
            <div>
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <span>💬</span> {text.nemotronAskTitle}
              </h3>
              <p className="text-xs text-slate-300 mt-1">{text.nemotronAskSubtitle}</p>
            </div>

            {/* Quick Suggestion Chips */}
            <div className="flex flex-wrap gap-2">
              {text.nemotronQuickPrompts.map((prompt, pIdx) => (
                <button
                  key={pIdx}
                  type="button"
                  disabled={qaLoading}
                  onClick={() => void handleAskQuestion(prompt)}
                  className="rounded-full border border-emerald-500/30 bg-emerald-950/40 px-3 py-1 text-xs text-emerald-200 hover:bg-emerald-900/60 hover:border-emerald-400 transition disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>

            {/* Chat History */}
            {qaHistory.length > 0 && (
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {qaHistory.map((item) => (
                  <div key={item.id} className="space-y-2">
                    {/* User Question */}
                    <div className="flex justify-end">
                      <div className="rounded-2xl rounded-br-sm bg-sky-600 px-4 py-2.5 text-sm text-white max-w-[85%] shadow-sm">
                        {item.question}
                      </div>
                    </div>
                    {/* Nemotron Answer */}
                    <div className="flex justify-start">
                      <div className="rounded-2xl rounded-bl-sm border border-emerald-500/30 bg-slate-950 px-4 py-3 text-sm text-slate-100 max-w-[90%] shadow-sm space-y-2">
                        <div className="flex items-center gap-2 text-xs font-mono text-emerald-400">
                          <span>NVIDIA Nemotron</span>
                          <span className="text-slate-500">· {item.timestamp}</span>
                        </div>
                        <p className="leading-relaxed whitespace-pre-wrap">{item.answer}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Error Message */}
            {qaError && (
              <div className="rounded-xl border border-red-500/40 bg-red-950/40 p-3 text-xs text-red-200 flex items-center justify-between">
                <span>{qaError}</span>
                <button
                  type="button"
                  onClick={() => setQaError("")}
                  className="underline ml-2"
                >
                  Dismiss
                </button>
              </div>
            )}

            {/* Question Input Form */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void handleAskQuestion();
              }}
              className="flex gap-2"
            >
              <input
                type="text"
                value={qaInput}
                onChange={(e) => setQaInput(e.target.value)}
                placeholder={text.nemotronPlaceholder}
                disabled={qaLoading}
                className="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400 transition"
              />
              <button
                type="submit"
                disabled={qaLoading || !qaInput.trim()}
                className="inline-flex items-center justify-center rounded-xl bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400 transition disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
              >
                {qaLoading ? text.nemotronAsking : text.nemotronAskBtn}
              </button>
            </form>
            <p className="text-[11px] text-slate-400 italic">
              {text.nemotronGroundedNotice}
            </p>
          </div>
        </section>

        {/* Video Technical Information */}
        <section className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5 sm:p-6">
          <h2 className="text-xl font-semibold">{text.info}</h2>
          <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-sm text-slate-400">{text.duration}</dt>
              <dd className="mt-1">{formatTime(video.video_info.duration_seconds)}</dd>
            </div>
            <div>
              <dt className="text-sm text-slate-400">{text.frames}</dt>
              <dd className="mt-1">
                {video.analyzed_frame_count} sampled / {video.scored_frame_count} scored
              </dd>
            </div>
            <div>
              <dt className="text-sm text-slate-400">{text.suspicious}</dt>
              <dd className="mt-1">{video.suspicious_signal_count}</dd>
            </div>
            <div>
              <dt className="text-sm text-slate-400">{text.audio}</dt>
              <dd className="mt-1">
                {video.video_info.has_audio ? video.video_info.audio_codec : "No audio stream"}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-slate-400">Resolution / FPS</dt>
              <dd className="mt-1">
                {video.video_info.width} × {video.video_info.height} · {video.video_info.fps} FPS
              </dd>
            </div>
            <div>
              <dt className="text-sm text-slate-400">Codec / container</dt>
              <dd className="mt-1">
                {video.video_info.video_codec} · {video.video_info.container}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-slate-400">Agreement</dt>
              <dd className="mt-1">{result.agreement}</dd>
            </div>
            <div>
              <dt className="text-sm text-slate-400">{text.audioNotAssessed}</dt>
              <dd className="mt-1">
                {video.video_info.audio_authenticity_assessed ? "Assessed" : "Not assessed"}
              </dd>
            </div>
          </dl>
        </section>

        {/* Forensic Evidence Timeline */}
        <section className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5 sm:p-6">
          <h2 className="text-xl font-semibold">{text.timeline}</h2>
          <p className="mt-2 text-sm text-amber-200">{text.signalNotice}</p>
          {video.frames.length ? (
            <ol className="mt-4 space-y-2">
              {video.frames.map((frame) => (
                <li key={`${frame.timestamp}-${frame.frame_index}`}>
                  <button
                    type="button"
                    onClick={() => seekTo(frame.timestamp)}
                    className="flex min-h-12 w-full flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-left hover:border-sky-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-300 transition"
                  >
                    <span className="font-mono text-sky-200">{formatTime(frame.timestamp)}</span>
                    <span>{frame.signal.replaceAll("_", " ")}</span>
                    <span className="text-sm text-slate-400">scene {frame.scene_id}</span>
                  </button>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-4 text-slate-300">No representative frames were available.</p>
          )}
          {notice && <p role="status" className="mt-3 text-sm text-amber-200">{notice}</p>}
          {video.scene_detection_status !== "ok" && (
            <p className="mt-3 text-sm text-slate-400">
              Scene-change detection was unavailable; frames were sampled uniformly.
            </p>
          )}
        </section>

        {/* Temporal & Face Tracking Checks */}
        <section className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5">
            <h2 className="text-lg font-semibold">{text.temporal}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">{video.temporal_checks.note}</p>
            <p className="mt-2 text-sm text-slate-400">
              Status: {video.temporal_checks.status}; unstable neighboring pairs:{" "}
              {video.temporal_checks.unstable_neighbor_pairs.length}.
            </p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5">
            <h2 className="text-lg font-semibold">{text.faces}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">{video.face_tracking.message}</p>
          </div>
        </section>

        {/* Not Checked & Limitations */}
        <section className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5">
            <h2 className="text-lg font-semibold">{text.notChecked}</h2>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-slate-300">
              {toList(video.what_was_not_checked).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5">
            <h2 className="text-lg font-semibold">{text.limitations}</h2>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-slate-300">
              {toList(video.limitations).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </section>

        <Link
          href="/"
          onClick={() => releaseVideoPreview(token)}
          className="inline-flex min-h-11 items-center rounded-xl border border-slate-700 bg-slate-950 px-4 py-2 text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-300 hover:border-slate-500 transition"
        >
          {text.back}
        </Link>
      </div>
    </main>
  );
}

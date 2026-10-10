"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { getVideoPreview, releaseVideoPreview } from "@/lib/video-preview-store";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

type VideoResult = {
  verdict: string;
  evidence_strength: string;
  agreement: string;
  explanation: Record<string, string>;
  tool_summaries: { video: VideoSummary };
};

const COPY = {
  en: {
    title: "Video authenticity investigation",
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
  },
  te: {
    title: "వీడియో ప్రామాణికత పరిశీలన",
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
  },
  hi: {
    title: "वीडियो प्रामाणिकता जाँच",
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
    videoRef.current.currentTime = timestamp;
    videoRef.current.pause();
    videoRef.current.focus();
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

  if (error) {
    return (
      <main className="min-h-screen px-4 py-10 text-slate-100 sm:px-6">
        <section role="alert" className="mx-auto max-w-3xl rounded-2xl border border-amber-400/30 bg-amber-500/10 p-6 text-amber-100">
          {error}
          <p className="mt-4"><Link className="underline" href="/">{text.back}</Link></p>
        </section>
      </main>
    );
  }
  if (!result) {
    return <p role="status" className="mx-auto max-w-4xl p-8 text-slate-300">{text.loading}</p>;
  }

  const video = result.tool_summaries.video;
  const localizedExplanation = result.explanation[language] ?? result.explanation.en;
  const warningClass = result.verdict === "Likely AI"
    ? "border-amber-400/40 bg-amber-500/10 text-amber-100"
    : "border-sky-400/30 bg-slate-900/70 text-slate-100";

  return (
    <main className="min-h-screen px-4 py-8 text-slate-100 sm:px-6 sm:py-12">
      <div className="mx-auto max-w-5xl space-y-6">
        <header className="rounded-3xl border border-sky-400/20 bg-slate-950/50 p-6 sm:p-8">
          <p className="text-xs uppercase tracking-[0.3em] text-sky-300">Very Frame AI</p>
          <h1 className="mt-3 text-3xl font-semibold text-white">{text.title}</h1>
        </header>

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
                  className="min-h-11 rounded-lg border border-slate-700 px-4 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-300"
                >
                  {code.toUpperCase()}
                </button>
              ))}
              <button type="button" onClick={() => void shareResult()} className="min-h-11 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950">
                {text.share}
              </button>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5 sm:p-6">
          <h2 className="text-xl font-semibold">{text.info}</h2>
          <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div><dt className="text-sm text-slate-400">{text.duration}</dt><dd className="mt-1">{formatTime(video.video_info.duration_seconds)}</dd></div>
            <div><dt className="text-sm text-slate-400">{text.frames}</dt><dd className="mt-1">{video.analyzed_frame_count} sampled / {video.scored_frame_count} scored</dd></div>
            <div><dt className="text-sm text-slate-400">{text.suspicious}</dt><dd className="mt-1">{video.suspicious_signal_count}</dd></div>
            <div><dt className="text-sm text-slate-400">{text.audio}</dt><dd className="mt-1">{video.video_info.has_audio ? video.video_info.audio_codec : "No audio stream"}</dd></div>
            <div><dt className="text-sm text-slate-400">Resolution / FPS</dt><dd className="mt-1">{video.video_info.width} × {video.video_info.height} · {video.video_info.fps} FPS</dd></div>
            <div><dt className="text-sm text-slate-400">Codec / container</dt><dd className="mt-1">{video.video_info.video_codec} · {video.video_info.container}</dd></div>
            <div><dt className="text-sm text-slate-400">Agreement</dt><dd className="mt-1">{result.agreement}</dd></div>
            <div><dt className="text-sm text-slate-400">{text.audioNotAssessed}</dt><dd className="mt-1">{video.video_info.audio_authenticity_assessed ? "Assessed" : "Not assessed"}</dd></div>
          </dl>
        </section>

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
                    className="flex min-h-12 w-full flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-left hover:border-sky-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-300"
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
            <p className="mt-3 text-sm text-slate-400">Scene-change detection was unavailable; frames were sampled uniformly.</p>
          )}
        </section>

        <section className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5">
            <h2 className="text-lg font-semibold">{text.temporal}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">{video.temporal_checks.note}</p>
            <p className="mt-2 text-sm text-slate-400">Status: {video.temporal_checks.status}; unstable neighboring pairs: {video.temporal_checks.unstable_neighbor_pairs.length}.</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5">
            <h2 className="text-lg font-semibold">{text.faces}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">{video.face_tracking.message}</p>
          </div>
        </section>

        <section className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5">
            <h2 className="text-lg font-semibold">{text.notChecked}</h2>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-slate-300">
              {video.what_was_not_checked.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5">
            <h2 className="text-lg font-semibold">{text.limitations}</h2>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-slate-300">
              {video.limitations.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </div>
        </section>
        <Link href="/" onClick={() => releaseVideoPreview(token)} className="inline-flex min-h-11 items-center rounded-xl border border-slate-700 bg-slate-950 px-4 py-2 text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-300">
          {text.back}
        </Link>
      </div>
    </main>
  );
}

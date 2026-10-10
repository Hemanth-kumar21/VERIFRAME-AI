"use client";

export type InvestigationEvent = {
  step: string;
  status: "pending" | "running" | "completed" | "failed" | "unavailable" | string;
  result?: unknown;
};

const STEP_DETAILS: Record<string, { title: string; description: string }> = {
  validate_input: {
    title: "Validating image",
    description: "Checking the supported format, file size, and image dimensions.",
  },
  investigation: {
    title: "Investigation",
    description: "Running the configured backend checks.",
  },
  validate_video: {
    title: "Validating video",
    description: "Checking the video file signature, declared format, and upload size.",
  },
  get_video_info: {
    title: "Reading video metadata",
    description: "Reading actual container, codec, duration, frame rate, resolution, and audio-stream metadata.",
  },
  detect_scenes: {
    title: "Detecting scenes",
    description: "Scanning downsampled video frames for scene changes using FFmpeg.",
  },
  sample_frames: {
    title: "Sampling representative frames",
    description: "Selecting a bounded set across the video duration and detected scene changes.",
  },
  assess_frame_quality: {
    title: "Assessing sampled-frame quality",
    description: "Checking each extracted frame for size, exposure, and basic image detail.",
  },
  run_frame_detectors: {
    title: "Running frame detectors",
    description: "Reusing configured image detectors on usable sampled frames.",
  },
  run_temporal_checks: {
    title: "Checking temporal evidence",
    description: "Comparing neighboring sampled-frame detector scores for instability.",
  },
  aggregate_evidence: {
    title: "Aggregating video evidence",
    description: "Applying conservative multi-frame and scene-coverage rules to the evidence.",
  },
  video_investigation: {
    title: "Video evidence explanation",
    description: "The configured language model may explain structured evidence; it cannot change the deterministic verdict.",
  },
  grounding_review: {
    title: "Grounding review",
    description: "Checking any model-generated explanation against structured video evidence.",
  },
  video_analysis: {
    title: "Video analysis",
    description: "Reporting whether the submitted video could be processed safely.",
  },
  save_result: {
    title: "Saving result",
    description: "Persisting the result summary and completed checks.",
  },
  write_explanation: {
    title: "Writing explanation",
    description: "Preparing a short explanation from reported evidence.",
  },
  review_evidence: {
    title: "Grounding review",
    description: "Checking that explanation claims match structured tool outputs.",
  },
  temporary_file_cleanup: {
    title: "Temporary-file cleanup",
    description: "Removing the temporary image file after processing.",
  },
  read_metadata: {
    title: "Metadata and provenance",
    description: "Checking available metadata and provenance without treating absence as evidence.",
  },
  check_c2pa: {
    title: "C2PA provenance",
    description: "Checking provenance when the verifier is available.",
  },
  get_file_info: {
    title: "File information",
    description: "Checking file properties returned by the backend.",
  },
  assess_quality: {
    title: "Image quality",
    description: "Checking whether image quality is sufficient for reliable analysis.",
  },
  run_detector_ensemble: {
    title: "AI-image detectors",
    description: "Reviewing the detector ensemble output.",
  },
  run_detector_a: {
    title: "Detector A",
    description: "Running one AI-image detection model.",
  },
  run_detector_b: {
    title: "Detector B",
    description: "Running an independent AI-image detection model.",
  },
  run_robustness_checks: {
    title: "Robustness checks",
    description: "Testing whether the result remains stable after small image changes.",
  },
  run_tile_analysis: {
    title: "Tile analysis",
    description: "Checking image regions for localized signals.",
  },
  extract_frames: {
    title: "Frame extraction",
    description: "Selecting representative frames from the video.",
  },
  analyze_frames: {
    title: "Frame analysis",
    description: "Checking selected frames for AI-generation signals.",
  },
  temporal_analysis: {
    title: "Temporal analysis",
    description: "Checking consistency across frames.",
  },
};

const STATUS: Record<string, { label: string; icon: string; style: string }> = {
  pending: { label: "Pending", icon: "○", style: "text-slate-400" },
  running: { label: "Running", icon: "◌", style: "text-sky-300" },
  completed: { label: "Completed", icon: "✓", style: "text-emerald-300" },
  complete: { label: "Completed", icon: "✓", style: "text-emerald-300" },
  failed: { label: "Failed", icon: "!", style: "text-rose-300" },
  unavailable: { label: "Unavailable", icon: "–", style: "text-amber-300" },
};

function describeResult(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const entries = Object.entries(value as Record<string, unknown>)
    .filter(([key, item]) => !["path", "filename"].includes(key.toLowerCase()) && item !== null)
    .slice(0, 3)
    .map(([key, item]) => `${key.replaceAll("_", " ")}: ${typeof item === "object" ? "available" : String(item)}`);
  return entries.length ? entries.join(" · ") : null;
}

export default function InvestigationTimeline({
  events,
}: {
  events: InvestigationEvent[];
}) {
  if (events.length === 0) {
    return (
      <p className="mt-4 rounded-xl border border-slate-700 bg-slate-950/60 p-3 text-sm text-slate-300">
        Investigation timeline is not available for this file.
      </p>
    );
  }

  return (
    <ol className="mt-5 space-y-4" aria-label="Investigation events">
      {events.map((event, index) => {
        const details = STEP_DETAILS[event.step];
        const status = STATUS[event.status] ?? {
          label: event.status,
          icon: "•",
          style: "text-slate-300",
        };
        return (
          <li key={`${event.step}-${index}`} className="flex gap-3">
            <span aria-hidden="true" className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-current ${status.style}`}>
              {status.icon}
            </span>
            <div className="min-w-0 flex-1 rounded-xl border border-slate-700 bg-slate-950/50 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="break-words font-medium text-white">{details?.title ?? event.step}</h3>
                <span className={`text-xs font-semibold uppercase tracking-wide ${status.style}`}>{status.label}</span>
              </div>
              <p className="mt-1 break-words text-sm leading-5 text-slate-300">
                {details?.description ?? "Backend-reported investigation event."}
              </p>
              {event.result !== undefined && event.result !== null && (
                <p className="mt-2 break-words text-xs leading-5 text-slate-400">
                  {describeResult(event.result)}
                </p>
              )}
              <details className="mt-2">
                <summary className="min-h-11 cursor-pointer py-2 text-xs text-slate-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-300">
                  Technical step: {event.step}
                </summary>
              </details>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

import { InformationPage, InformationSection } from "@/components/information-page";

const imageSteps = [
  ["Upload and validate", "The API accepts an image and checks its file signature, size, image decoding, and dimensions."],
  ["Inspect file and quality", "The backend records file details and checks image resolution and basic quality signals."],
  ["Read metadata and provenance", "The backend reads EXIF availability and checks whether C2PA can be verified in its environment."],
  ["Run configured detectors", "The backend runs the configured Hugging Face image-classification models (two distinct models are required for a verdict); their scores are not calibrated probabilities."],
  ["Check robustness and regions", "The backend runs transformed-image checks and experimental tile analysis."],
  ["Aggregate and explain", "The verdict pipeline combines detector outputs, quality, and robustness into a cautious verdict and stored report."],
];

export default function HowItWorksPage() {
  return (
    <InformationPage
      title="How it works"
      intro="Image and video use separate backend pipelines. The video path samples bounded frames, checks available signals across time, and retains only structured results."
    >
      <ol className="space-y-4">
        {imageSteps.map(([title, description], index) => (
          <li key={title} className="flex gap-4 rounded-2xl border border-slate-700 bg-slate-900/70 p-4 sm:p-5">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-sky-400/40 text-sm font-semibold text-sky-200" aria-label={`Step ${index + 1}`}>
              {index + 1}
            </span>
            <div className="min-w-0">
              <h2 className="break-words font-semibold text-white">{title}</h2>
              <p className="mt-1 break-words text-sm leading-6 text-slate-300">{description}</p>
            </div>
          </li>
        ))}
      </ol>
      <InformationSection title="Video analysis">
        <p>
          The video API inspects container/codec metadata with ffprobe, detects scene changes with
          FFmpeg, combines uniform and scene-change sampling within a configurable frame budget,
          filters unusable frames, then reuses the configured image-classification detectors on sampled
          frames. The deterministic verdict requires multi-frame evidence and sufficient scene coverage;
          sparse or unstable evidence remains inconclusive. The result timeline seeks the in-tab local
          preview to evidence timestamps when that preview remains available.
        </p>
      </InformationSection>
      <InformationSection title="What is not implemented">
        <p>
          Face detection/tracking, audio authenticity, audio/video synchronization, and motion
          consistency models are unavailable. The optional language model can draft a short explanation
          from structured video evidence and an independent grounding review can reject it; the model
          does not choose the video tools or override the deterministic verdict. A VISION_MODEL call
          for image analysis can send that image to the configured provider. Model IDs and labels must
          be verified by the operator; the project does not provide a verified Nemotron model ID.
        </p>
      </InformationSection>
    </InformationPage>
  );
}

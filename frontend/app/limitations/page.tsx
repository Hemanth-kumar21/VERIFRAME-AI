import { InformationPage, InformationSection } from "@/components/information-page";

export default function LimitationsPage() {
  return (
    <InformationPage
      title="Limitations"
      intro="Very Frame AI reports evidence from the checks currently implemented by this project. A verdict is an aid to review, not a guarantee about how media was created."
    >
      <InformationSection title="Detection is imperfect">
        <ul className="list-disc space-y-2 pl-5">
          <li>AI detectors can make mistakes, and newer generation methods may be difficult to detect.</li>
          <li>The backend can run configured Hugging Face image-classification models. No detector model IDs or labels are pre-verified by this repository; the operator must inspect and configure them.</li>
          <li>Model outputs are experimental evidence, not proof, and scores are not calibrated probabilities.</li>
          <li>Compression, resizing, editing, and screenshots can change image signals or remove metadata.</li>
          <li>Missing provenance does not prove that a file was AI-generated or that it is authentic.</li>
          <li>Video verdicts use configured frame classifiers sampled across the clip and deterministic score-distribution/neighbor-stability checks; this does not establish identity consistency or prove manipulation.</li>
          <li>Face detection/tracking, audio authenticity, audio/video synchronization, and deepfake-specific temporal models are not implemented.</li>
          <li>FFmpeg/ffprobe must be installed on the backend PATH. Codec support depends on that FFmpeg build, and a configured size/duration/resolution/FPS budget still applies.</li>
          <li>Optional language-model use is limited to explaining structured video evidence; it does not select video tools or change the deterministic verdict. No verified Nemotron model ID is supplied.</li>
          <li>Only checks recorded in the result trace should be considered completed.</li>
        </ul>
      </InformationSection>
      <InformationSection title="Benchmark and calibration">
        <p>
          Not yet evaluated. This checkout has no measured benchmark results or usable calibration system.
          Do not interpret raw detector scores as percentages, accuracy, or certainty.
        </p>
      </InformationSection>
      <InformationSection title="Generator identification">
        <p>
          The current provenance reader reports EXIF and C2PA availability only; it does not report a
          verified generator identity. The result page therefore does not identify a generator.
        </p>
      </InformationSection>
    </InformationPage>
  );
}

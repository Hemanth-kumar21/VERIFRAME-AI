import { InformationPage, InformationSection } from "@/components/information-page";

export default function PrivacyPage() {
  return (
    <InformationPage
      title="Privacy"
      intro="This page describes behavior visible in the current Very Frame AI backend. Deployment operators should review their own infrastructure, backups, and logs before making additional promises."
    >
      <InformationSection title="Media processing">
        <p>
          The image analysis endpoint reads the uploaded image into backend memory, writes a temporary
          file for analysis, and removes that temporary file in its cleanup step. Video uploads are
          staged in a backend temporary file; FFmpeg-extracted frames are also temporary. Both are
          deleted in cleanup paths. The server does not retain the uploaded video or extracted frames.
          The original video preview is held in browser memory during the current tab&apos;s result journey;
          refreshing or leaving the page may make that local preview unavailable.
        </p>
      </InformationSection>
      <InformationSection title="Stored information">
        <p>
          The backend stores investigation results, including verdict, evidence summaries, trace,
          explanations, provider metadata, and a timestamp, in a local SQLite database. User reports
          store the result token, category, comment, and timestamp. No retention period or automatic
          deletion policy is configured in this checkout.
        </p>
      </InformationSection>
      <InformationSection title="Aggregate information and external services">
        <p>
          The insights endpoint returns aggregate analysis counts and verdict distribution. The backend
          contacts the configured model provider for a status check and may use it for tool selection
          or explanation when enabled. The optional VISION_MODEL tool can send the uploaded image
          itself to that configured provider if it is enabled and called. A configured language model
          may receive structured video metadata, sampled-frame scores, timeline timestamps, and the
          deterministic verdict to draft an explanation; it is not given the uploaded video by the
          video investigator. Configured Hugging Face classifiers run through the local Transformers
          pipeline; their weights may be downloaded from the model registry. Review provider terms and model sources before enabling them. No
          analytics or advertising tracker integration was found in the application source inspected
          for this release.
        </p>
      </InformationSection>
      <InformationSection title="Credentials and uncertainty">
        <p>
          Provider credentials are read by the backend from environment configuration and are not
          intentionally exposed to browser code. Results communicate uncertainty and do not prove
          authorship or authenticity. Actual retention and access controls depend on the deployment.
        </p>
      </InformationSection>
    </InformationPage>
  );
}

import { Suspense } from "react";
import VideoResultView from "@/components/video-result-view";

async function VideoResultContent({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <VideoResultView token={token} />;
}

export default function VideoResultPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  return (
    <Suspense fallback={<p role="status" className="mx-auto max-w-4xl p-8">Loading video investigation…</p>}>
      <VideoResultContent params={params} />
    </Suspense>
  );
}

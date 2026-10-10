"use client";

import {
  ChangeEvent,
  DragEvent,
  FormEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import InvestigationTimeline, {
  InvestigationEvent,
} from "@/components/investigation-timeline";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const MAX_IMAGE_PIXELS = 10_000_000;

type VideoConfig = {
  available: boolean;
  formats: string[];
  max_size_mb: number;
  max_duration_seconds: number;
  max_resolution: string;
  max_fps: number;
  max_analyzed_frames: number;
  analysis_timeout_seconds: number;
  message: string;
};

function getImageFormat(bytes: Uint8Array): "PNG" | "JPEG" | "WEBP" | null {
  if (
    bytes.length >= 8 &&
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47 &&
    bytes[4] === 0x0d &&
    bytes[5] === 0x0a &&
    bytes[6] === 0x1a &&
    bytes[7] === 0x0a
  ) {
    return "PNG";
  }
  if (bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) {
    return "JPEG";
  }
  if (
    bytes.length >= 12 &&
    String.fromCharCode(...bytes.slice(0, 4)) === "RIFF" &&
    String.fromCharCode(...bytes.slice(8, 12)) === "WEBP"
  ) {
    return "WEBP";
  }
  return null;
}

function readImageDimensions(url: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const image = document.createElement("img");
    image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight });
    image.onerror = () => reject(new Error("This file is corrupt or cannot be opened as an image."));
    image.src = url;
  });
}

function readVideoMetadata(url: string): Promise<{ duration: number; width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const video = document.createElement("video");
    video.preload = "metadata";
    video.onloadedmetadata = () =>
      resolve({
        duration: video.duration,
        width: video.videoWidth,
        height: video.videoHeight,
      });
    video.onerror = () => reject(new Error("Video preview metadata could not be read in this browser."));
    video.src = url;
  });
}

async function readInvestigationEvents(
  token: string,
  onEvent: (event: InvestigationEvent) => void,
  route = "analyze",
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/${route}/${encodeURIComponent(token)}/events`,
  );
  if (!response.ok || !response.body) throw new Error("Investigation events are unavailable.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatchBlock = (block: string) => {
    const data = block
      .split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trim())
      .join("\n");
    if (!data) return;
    try {
      const payload = JSON.parse(data) as Partial<InvestigationEvent>;
      if (typeof payload.step !== "string" || typeof payload.status !== "string") return;
      onEvent({
        step: payload.step,
        status: payload.status,
        ...(payload.result !== undefined ? { result: payload.result } : {}),
      });
    } catch {
      // Ignore malformed server events; they do not represent a verified step.
    }
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() ?? "";
      blocks.forEach(dispatchBlock);
      if (done) break;
    }
    if (buffer.trim()) dispatchBlock(buffer);
  } finally {
    reader.releaseLock();
  }
}

export default function HomePage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedVideo, setSelectedVideo] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageDimensions, setImageDimensions] = useState<{ width: number; height: number } | null>(
    null,
  );
  const [videoMetadata, setVideoMetadata] = useState<{
    duration: number;
    width: number;
    height: number;
  } | null>(null);
  const [videoConfig, setVideoConfig] = useState<VideoConfig | null>(null);
  const [videoConfigError, setVideoConfigError] = useState("");
  const [videoMetadataError, setVideoMetadataError] = useState("");
  const [language, setLanguage] = useState("en");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [investigationEvents, setInvestigationEvents] = useState<InvestigationEvent[]>([]);
  const [isLoadingEvents, setIsLoadingEvents] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Ready for a fresh image check.");
  const [hasError, setHasError] = useState(false);
  const previewUrlRef = useRef<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const videoInputRef = useRef<HTMLInputElement>(null);
  const videoCameraInputRef = useRef<HTMLInputElement>(null);
  const dragDepthRef = useRef(0);
  const selectionIdRef = useRef(0);
  const router = useRouter();

  useEffect(
    () => () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    },
    [],
  );

  useEffect(() => {
    const controller = new AbortController();
    void fetch(`${API_BASE_URL}/api/video/config`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Video configuration is unavailable.");
        const config = (await response.json()) as VideoConfig;
        if (
          typeof config.available !== "boolean" ||
          typeof config.max_size_mb !== "number" ||
          typeof config.max_duration_seconds !== "number" ||
          typeof config.max_analyzed_frames !== "number" ||
          typeof config.analysis_timeout_seconds !== "number"
        ) {
          throw new Error("The backend returned invalid video limits.");
        }
        setVideoConfig(config);
        setVideoConfigError("");
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setVideoConfig(null);
          setVideoConfigError("Video limits could not be loaded from the backend.");
        }
      });
    return () => controller.abort();
  }, []);

  const setStatus = (message: string, isError = false) => {
    setStatusMessage(message);
    setHasError(isError);
  };

  const validateAndSelectFile = async (file: File) => {
    const selectionId = ++selectionIdRef.current;
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = null;
    setPreviewUrl(null);
    setSelectedVideo(null);
    setSelectedFile(null);
    setVideoMetadataError("");
    setImageDimensions(null);
    setVideoMetadata(null);
    setInvestigationEvents([]);

    if (file.size === 0) {
      setStatus("This image file is empty. Choose another image.", true);
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setStatus("Image exceeds the 10 MB limit. Choose a smaller image.", true);
      return;
    }

    try {
      const header = new Uint8Array(await file.slice(0, 12).arrayBuffer());
      const format = getImageFormat(header);
      if (!format) {
        setStatus("Unsupported image type. Choose a PNG, JPEG, or WEBP image.", true);
        return;
      }

      const temporaryUrl = URL.createObjectURL(file);
      let dimensions: { width: number; height: number };
      try {
        dimensions = await readImageDimensions(temporaryUrl);
      } finally {
        URL.revokeObjectURL(temporaryUrl);
      }

      if (selectionId !== selectionIdRef.current) return;
      if (
        dimensions.width <= 0 ||
        dimensions.height <= 0 ||
        dimensions.width * dimensions.height > MAX_IMAGE_PIXELS
      ) {
        setStatus("Image dimensions exceed the 10 million pixel limit. Choose a smaller image.", true);
        return;
      }

      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = URL.createObjectURL(file);
      setPreviewUrl(previewUrlRef.current);
      setSelectedFile(file);
      setImageDimensions(dimensions);
      setStatus(`${file.name || `Pasted ${format} image`} is ready for investigation.`);
    } catch (error) {
      if (selectionId !== selectionIdRef.current) return;
      const message =
        error instanceof Error ? error.message : "The image could not be checked. Try another file.";
      setStatus(message, true);
    }
  };

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.currentTarget.value = "";
    if (file) void validateAndSelectFile(file);
  };

  const selectVideo = async (file: File) => {
    selectionIdRef.current += 1;
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = null;
    setPreviewUrl(null);
    setSelectedFile(null);
    setSelectedVideo(null);
    setImageDimensions(null);
    setVideoMetadata(null);
    setInvestigationEvents([]);
    if (!file.size) {
      setStatus("This video file is empty. Choose another file.", true);
      return;
    }
    const url = URL.createObjectURL(file);
    previewUrlRef.current = url;
    setPreviewUrl(url);
    setSelectedFile(null);
    setSelectedVideo(file);
    setImageDimensions(null);
    setVideoMetadata(null);
    setVideoMetadataError("");
    setInvestigationEvents([]);
    setSelectedVideo(file);
    try {
      const metadata = await readVideoMetadata(url);
      if (previewUrlRef.current !== url) return;
      setVideoMetadata(metadata);
      setStatus("Video selected. Server-side container and codec checks run before frame analysis.");
    } catch {
      if (previewUrlRef.current !== url) return;
      setVideoMetadataError("Video metadata could not be read in this browser.");
      setStatus("Video metadata could not be read in this browser.", true);
    }
  };

  const onVideoChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.currentTarget.value = "";
    if (file) void selectVideo(file);
  };

  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      if (isSubmitting) return;
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        (target.isContentEditable ||
          ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
      ) {
        return;
      }

      const items = Array.from(event.clipboardData?.items ?? []);
      const imageItem = items.find((item) => item.type.startsWith("image/"));
      const file = imageItem?.getAsFile();
      if (!file) return;

      event.preventDefault();
      const extension =
        file.type === "image/jpeg" ? "jpg" : file.type === "image/webp" ? "webp" : "png";
      const pastedFile = new File([file], file.name || `pasted-image.${extension}`, {
        type: file.type,
        lastModified: Date.now(),
      });
      void validateAndSelectFile(pastedFile);
    };

    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  });

  const onDragEnter = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (isSubmitting) return;
    dragDepthRef.current += 1;
    setIsDragging(true);
  };

  const onDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
  };

  const onDragLeave = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) setIsDragging(false);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    dragDepthRef.current = 0;
    setIsDragging(false);
    if (isSubmitting) return;
    const files = Array.from(event.dataTransfer.files);
    const file = files.find(
      (item) =>
        item.type.startsWith("image/") ||
        item.type.startsWith("video/") ||
        /\.(mp4|m4v|mov|webm|avi|mkv|mpeg|mpg|3gp)$/i.test(item.name),
    );
    if (!file) {
      setStatus("No supported media file found. Drop an image or video file here.", true);
      return;
    }
    if (file.type.startsWith("video/") || /\.(mp4|m4v|mov|webm|avi|mkv|mpeg|mpg|3gp)$/i.test(file.name)) {
      void selectVideo(file);
    } else {
      void validateAndSelectFile(file);
    }
  };

  const clearSelection = () => {
    selectionIdRef.current += 1;
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = null;
    setPreviewUrl(null);
    setSelectedFile(null);
    setSelectedVideo(null);
    setImageDimensions(null);
    setVideoMetadata(null);
    setVideoMetadataError("");
    setInvestigationEvents([]);
    setStatus("Ready for a fresh image check.");
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (selectedVideo) {
      if (videoSelectionError) {
        setStatus(videoSelectionError, true);
        return;
      }
      if (!videoConfig?.available) {
        setStatus(
          videoConfig?.message ??
            "Video limits and FFmpeg support have not been confirmed by the backend.",
          true,
        );
        return;
      }
      const formData = new FormData();
      formData.append("file", selectedVideo);
      formData.append("lang", language);
      setIsSubmitting(true);
      setInvestigationEvents([]);
      setIsLoadingEvents(false);
      setStatus("Uploading video to the backend for validation and analysis...");
      try {
        const response = await fetch(`${API_BASE_URL}/api/video/analyze`, {
          method: "POST",
          body: formData,
          signal: AbortSignal.timeout((videoConfig.analysis_timeout_seconds + 60) * 1000),
        });
        const payload = (await response.json().catch(() => null)) as
          | { token?: string; job_id?: string; detail?: string }
          | null;
        if (!response.ok) throw new Error(payload?.detail ?? "The video analysis request failed.");
        const token = payload?.token ?? payload?.job_id;
        if (!token) throw new Error("The video API did not return a result token.");

        let processingError = "";
        setIsLoadingEvents(true);
        try {
          await readInvestigationEvents(
            token,
            (analysisEvent) => {
              setInvestigationEvents((previous) => [...previous, analysisEvent]);
              setStatus(
                `Video analysis: ${analysisEvent.step.replaceAll("_", " ")} — ${analysisEvent.status}.`,
                analysisEvent.status === "failed",
              );
              if (analysisEvent.status === "failed") {
                processingError =
                  typeof analysisEvent.result === "string"
                    ? analysisEvent.result
                    : "The backend could not analyze this video.";
              }
            },
            "video/analyze",
          );
        } finally {
          setIsLoadingEvents(false);
        }
        if (processingError) throw new Error(processingError);

        const resultResponse = await fetch(
          `${API_BASE_URL}/api/video/result/${encodeURIComponent(token)}`,
          { signal: AbortSignal.timeout(20_000) },
        );
        if (!resultResponse.ok) {
          throw new Error("The backend did not make the completed video result available.");
        }
        const savedResult = (await resultResponse.json().catch(() => null)) as
          | { verdict?: unknown }
          | null;
        if (!savedResult || typeof savedResult.verdict !== "string") {
          throw new Error("The backend returned an invalid video investigation result.");
        }
        const { retainVideoPreview } = await import("@/lib/video-preview-store");
        if (previewUrlRef.current) {
          retainVideoPreview(token, previewUrlRef.current);
          previewUrlRef.current = null;
        }
        setStatus("Video investigation complete. Opening the evidence report.");
        router.push(`/video/result/${encodeURIComponent(token)}`);
      } catch (error) {
        const message =
          error instanceof DOMException && error.name === "TimeoutError"
            ? "Video analysis exceeded its time limit. Try a shorter video."
            : error instanceof TypeError
              ? "The video analysis service could not be reached. Check your connection and try again."
              : error instanceof Error
                ? error.message
                : "Video analysis failed. Try again later.";
        setStatus(message, true);
      } finally {
        setIsSubmitting(false);
      }
      return;
    }

    if (!selectedFile) {
      setStatus(
        "Choose or paste an image, or select a supported video first.",
        true,
      );
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("lang", language);

    setIsSubmitting(true);
    setInvestigationEvents([]);
    setIsLoadingEvents(false);
    setStatus("Uploading image and waiting for the backend investigation...");

    try {
      const response = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: "POST",
        body: formData,
        signal: AbortSignal.timeout(180_000),
      });

      const payload = (await response.json().catch(() => null)) as
        | { token?: string; job_id?: string; detail?: string }
        | null;

      if (!response.ok) {
        throw new Error(payload?.detail ?? "The analysis request failed.");
      }

      const token = payload?.token ?? payload?.job_id;
      if (!token) {
        throw new Error("The API did not return a result token.");
      }

      setStatus("Image upload completed. Waiting for recorded backend investigation events...");
      setIsLoadingEvents(true);
      try {
        await readInvestigationEvents(token, (event) => {
          setInvestigationEvents((previous) => [...previous, event]);
          setStatus(`Backend event: ${event.step} — ${event.status}.`);
        });
      } catch {
        setStatus("The investigation timeline is unavailable. Verifying the saved result...");
      } finally {
        setIsLoadingEvents(false);
      }

      const resultResponse = await fetch(
        `${API_BASE_URL}/api/result/${encodeURIComponent(token)}`,
        { signal: AbortSignal.timeout(20_000) },
      );
      if (!resultResponse.ok) {
        throw new Error("The backend did not make the completed result available.");
      }
      const savedResult = (await resultResponse.json().catch(() => null)) as
        | { verdict?: unknown }
        | null;
      if (!savedResult || typeof savedResult.verdict !== "string") {
        throw new Error("The backend returned an invalid investigation result.");
      }
      setStatus("Investigation complete. Opening the verified result.");
      router.push(`/result/${token}`);
    } catch (error) {
      const message =
        error instanceof DOMException && error.name === "TimeoutError"
          ? "The investigation timed out before a result was available. Try again later."
          : error instanceof TypeError
            ? "The investigation service could not be reached. Check your connection and try again."
            : error instanceof Error
              ? `${error.message} Check the file and try again.`
              : "The investigation could not be completed. Try again later.";
      setStatus(message, true);
    } finally {
      setIsSubmitting(false);
    }
  };

  const videoSelectionError = !selectedVideo
    ? ""
    : videoMetadataError ||
      videoConfigError ||
      (!videoConfig
        ? "Waiting for video limits and FFmpeg support from the backend."
        : !videoConfig.available
          ? videoConfig.message
          : selectedVideo.size > videoConfig.max_size_mb * 1024 * 1024
            ? `Video exceeds the ${videoConfig.max_size_mb} MB size limit.`
            : !videoMetadata
              ? "Reading video duration and resolution before upload."
              : videoMetadata.duration > videoConfig.max_duration_seconds
                ? `Video exceeds the ${videoConfig.max_duration_seconds}-second duration limit.`
                : "");

  return (
    <main className="min-h-screen px-4 py-6 text-slate-100 sm:px-6 sm:py-10">
      <div className="mx-auto flex max-w-6xl flex-col gap-8">
        <header className="flex flex-col gap-4 rounded-3xl border border-sky-400/20 bg-slate-950/40 p-6 backdrop-blur-sm sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-sky-300">Very Frame AI</p>
            <h1 className="mt-3 text-3xl font-semibold text-white sm:text-4xl">
              Media evidence review for AI-generated or altered content
            </h1>
          </div>
          <div className="w-fit rounded-full border border-sky-400/30 bg-sky-500/10 px-4 py-2 text-sm text-sky-100">
            Evidence-led review
          </div>
        </header>

        <section className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
          <form
            onSubmit={onSubmit}
            className="rounded-3xl border border-white/10 bg-slate-900/60 p-5 shadow-2xl shadow-sky-950/30 sm:p-6"
          >
            <div className="mb-6 flex items-center justify-between gap-3">
              <h2 className="text-xl font-semibold text-white">Choose media</h2>
              <span className="rounded border border-sky-500/40 bg-sky-500/10 px-2 py-1 text-xs uppercase tracking-[0.25em] text-sky-200">
                secure review
              </span>
            </div>

            <div
              onDragEnter={onDragEnter}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
              className={`rounded-2xl border border-dashed p-6 text-center transition sm:p-8 ${
                isDragging
                  ? "border-sky-300 bg-sky-500/10"
                  : "border-sky-400/50 bg-slate-950/60"
              }`}
            >
              <input
                ref={fileInputRef}
                id="image-file"
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="sr-only"
                onChange={onFileChange}
                disabled={isSubmitting}
                aria-label="Choose an image file"
              />
              <input
                ref={cameraInputRef}
                id="camera-file"
                type="file"
                accept="image/*"
                capture="environment"
                className="sr-only"
                onChange={onFileChange}
                disabled={isSubmitting}
                aria-label="Take a photo"
              />
              <input
                ref={videoInputRef}
                id="video-file"
                type="file"
                accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm"
                className="sr-only"
                onChange={onVideoChange}
                disabled={isSubmitting}
                aria-label="Choose a video from your device"
              />
              <input
                ref={videoCameraInputRef}
                id="video-camera-file"
                type="file"
                accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm"
                capture="environment"
                className="sr-only"
                onChange={onVideoChange}
                disabled={isSubmitting}
                aria-label="Capture or select a video"
              />

              {previewUrl && selectedVideo ? (
                <div className="relative mx-auto mb-5 max-w-xl overflow-hidden rounded-xl border border-white/10 bg-slate-950">
                  <video
                    src={previewUrl}
                    controls
                    playsInline
                    preload="metadata"
                    aria-label={`Video preview: ${selectedVideo.name}`}
                    className="max-h-80 w-full bg-black object-contain"
                  >
                    Video preview is not supported by this browser.
                  </video>
                  <dl className="grid gap-2 p-3 text-left text-xs text-slate-300 sm:grid-cols-2">
                    <div className="break-words"><dt className="inline font-semibold">File: </dt><dd className="inline">{selectedVideo.name}</dd></div>
                    <div><dt className="inline font-semibold">Size: </dt><dd className="inline">{(selectedVideo.size / (1024 * 1024)).toFixed(2)} MB</dd></div>
                    <div><dt className="inline font-semibold">Format: </dt><dd className="inline">{selectedVideo.type || "Browser format not reported"}</dd></div>
                    {videoMetadata && (
                      <>
                        <div><dt className="inline font-semibold">Duration: </dt><dd className="inline">{Number.isFinite(videoMetadata.duration) ? `${Math.floor(videoMetadata.duration / 60)}:${String(Math.floor(videoMetadata.duration % 60)).padStart(2, "0")}` : "Unavailable"}</dd></div>
                        <div><dt className="inline font-semibold">Resolution: </dt><dd className="inline">{videoMetadata.width} × {videoMetadata.height}</dd></div>
                      </>
                    )}
                  </dl>
                </div>
              ) : previewUrl && selectedFile ? (
                <div className="mx-auto mb-5 max-w-md">
                  <Image
                    src={previewUrl}
                    alt={`Preview of ${selectedFile?.name ?? "selected image"}`}
                    width={640}
                    height={480}
                    unoptimized
                    className="max-h-72 w-full rounded-xl border border-white/10 object-contain"
                  />
                  {imageDimensions && (
                    <p className="mt-2 text-xs text-slate-400">
                      {imageDimensions.width} × {imageDimensions.height} pixels
                    </p>
                  )}
                </div>
              ) : (
                <div aria-hidden="true" className="mb-4 text-3xl text-sky-200">
                  ⬆
                </div>
              )}
              <p className="break-words text-lg font-medium text-white">
                {selectedVideo?.name ?? selectedFile?.name ?? "Choose or drop an image or video"}
              </p>
              <p className="mt-2 text-sm text-slate-400">
                Drop media here, choose a file, or paste an image with Ctrl+V.
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Images: maximum 10 MB and 10 million pixels. Videos: MP4, MOV, or WebM when FFmpeg supports the codec.
                {videoConfig && ` Maximum ${videoConfig.max_size_mb} MB, ${Math.floor(videoConfig.max_duration_seconds / 60)} minutes, ${videoConfig.max_resolution}, ${videoConfig.max_fps} FPS, and ${videoConfig.max_analyzed_frames} sampled frames.`}
              </p>

              {selectedVideo && (
                <p role={videoSelectionError ? "alert" : "status"} className="mt-4 rounded-xl border border-amber-400/30 bg-amber-500/10 p-3 text-left text-sm leading-6 text-amber-100">
                  {videoSelectionError || videoConfig?.message || "Checking video-analysis support…"}
                </p>
              )}

              <div className="mt-5 flex flex-col justify-center gap-3 sm:flex-row sm:flex-wrap">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isSubmitting}
                  className="min-h-11 rounded-xl border border-sky-400/40 bg-sky-500/10 px-4 py-2.5 text-sm font-medium text-sky-100 transition hover:border-sky-300 hover:bg-sky-500/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Choose image
                </button>
                <button
                  type="button"
                  onClick={() => cameraInputRef.current?.click()}
                  disabled={isSubmitting}
                  className="min-h-11 rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:border-slate-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300 disabled:cursor-not-allowed disabled:opacity-60 sm:hidden"
                >
                  Take a photo
                </button>
                <button
                  type="button"
                  onClick={() => videoInputRef.current?.click()}
                  disabled={isSubmitting}
                  className="min-h-11 rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:border-slate-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Choose video
                </button>
                <button
                  type="button"
                  onClick={() => videoCameraInputRef.current?.click()}
                  disabled={isSubmitting}
                  className="min-h-11 rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:border-slate-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300 disabled:cursor-not-allowed disabled:opacity-60 sm:hidden"
                >
                  Capture video
                </button>
              </div>
            </div>

            <div className="mt-6">
              <label htmlFor="language" className="mb-2 block text-sm font-medium text-slate-200">
                Explanation language
              </label>
              <select
                id="language"
                value={language}
                onChange={(event) => setLanguage(event.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-base text-white outline-none ring-0 transition focus:border-sky-400"
              >
                <option value="en">English</option>
                <option value="hi">Hindi</option>
                <option value="te">Telugu</option>
              </select>
            </div>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <button
                type="submit"
                disabled={isSubmitting || (Boolean(selectedVideo) && Boolean(videoSelectionError))}
                className="flex-1 rounded-xl bg-sky-500 px-5 py-3 text-base font-semibold text-slate-950 transition hover:bg-sky-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? "Waiting for backend..." : selectedVideo ? "Run video investigation" : "Run forensic review"}
              </button>
              <button
                type="button"
                onClick={clearSelection}
                disabled={isSubmitting}
                className="rounded-xl border border-slate-700 bg-slate-950 px-5 py-3 text-base font-medium text-slate-200 transition hover:border-slate-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Clear
              </button>
            </div>

            <p
              role={hasError ? "alert" : "status"}
              aria-live={hasError ? "assertive" : "polite"}
              className={`mt-5 rounded-xl border px-4 py-3 text-sm ${
                hasError
                  ? "border-rose-400/30 bg-rose-500/10 text-rose-200"
                  : "border-slate-700 bg-slate-950/40 text-slate-300"
              }`}
            >
              {statusMessage}
            </p>
            <p className="mt-3 break-words text-xs leading-5 text-slate-400">
              Image and video uploads are temporarily staged for backend analysis and removed in cleanup. The backend stores structured investigation results and evidence summaries. The browser video preview remains local to this tab.
            </p>
            {isSubmitting && (
              <div className="mt-4 rounded-2xl border border-sky-400/20 bg-slate-950/50 p-4" aria-busy="true">
                <div className="flex items-center gap-3">
                  <span className="scan-indicator h-2 w-2 shrink-0 rounded-full bg-sky-300" aria-hidden="true" />
                  <p className="text-sm font-medium text-sky-100">Uploading and waiting for the backend investigation response</p>
                </div>
                <p className="mt-2 text-xs text-slate-400">No investigation steps are shown until the backend reports them.</p>
                {isLoadingEvents && (
                  <div className="mt-4 border-t border-slate-800 pt-3">
                    <p className="text-sm font-medium text-white">Recorded investigation events</p>
                    <InvestigationTimeline events={investigationEvents} />
                  </div>
                )}
              </div>
            )}
          </form>

          <aside className="rounded-3xl border border-white/10 bg-slate-900/60 p-6">
            <h2 className="text-xl font-semibold text-white">Checklist</h2>
            <ul className="mt-5 space-y-4 text-sm text-slate-300">
              <li className="flex gap-3">
                <span className="mt-1 text-sky-300">✓</span>
                <span>Validates file type, size, and image structure before analysis.</span>
              </li>
              <li className="flex gap-3">
                <span className="mt-1 text-sky-300">✓</span>
                <span>Assesses quality, metadata, and manipulation heuristics.</span>
              </li>
              <li className="flex gap-3">
                <span className="mt-1 text-sky-300">✓</span>
                <span>Reports a verdict using a conservative evidence-led pipeline.</span>
              </li>
              <li className="flex gap-3">
                <span className="mt-1 text-sky-300">✓</span>
                <span>Supports English, Hindi, and Telugu explanations.</span>
              </li>
            </ul>
          </aside>
        </section>
      </div>
    </main>
  );
}

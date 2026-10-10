# Very Frame AI

Very Frame AI is an evidence-led image and video review application. It reports the checks performed by the configured backend; a verdict is an estimate, not proof of authenticity or AI generation.

## Implemented capabilities

- Image selection, drag and drop, clipboard paste, camera/gallery selection, preview, and browser-side validation.
- Backend validation for PNG, JPEG, and WEBP: size, matching MIME/extension/signature, full image decoding, and dimensions.
- Configurable image byte and pixel ceilings. Defaults are 10 MiB and 10 megapixels.
- A background image-analysis job with progress events from the backend, persisted results, and result links.
- Configurable Hugging Face image-classification adapters. Two distinct models with operator-verified AI labels are required for a non-inconclusive verdict. No detector model IDs or labels are preselected as verified by this repository.
- Conservative verdict logic, evidence summaries, translated explanations (English, Telugu, Hindi), feedback reports, and PNG share cards that do not contain the original image.
- Token-protected aggregate insights, an empty-by-default sample gallery, and a PWA manifest/service worker with an offline information page.
- MP4, MOV, and WebM can be submitted when FFmpeg/ffprobe are installed and the particular codec is decodable by that FFmpeg build. The API validates the container signature, metadata, duration, resolution, frame rate, and configured size limits.
- Video checks use bounded uniform and scene-change frame sampling, frame quality assessment, the existing configured image detector abstraction, neighboring sampled-frame score consistency, and conservative deterministic aggregation. A sparse signal from one frame cannot alone produce a Likely AI verdict.
- Video results include an evidence timeline that seeks the browser's current-tab local preview. The upload, temporary FFmpeg frames, and extracted processing files are not retained after analysis. Results persist structured metadata and evidence summaries only.
- The optional configured language model can draft an explanation from structured video evidence; the existing grounding reviewer can reject it. It cannot select video tools or override the deterministic verdict. No verified Nemotron model ID is supplied.
- Video face detection/tracking, audio authenticity, audio/video synchronization, and deepfake-specific motion analysis are not implemented. Audio presence/codec is metadata only.

Model outputs and thresholds have not been calibrated against a labeled benchmark. Do not interpret a raw score as a probability. The configured optional language model is not itself the verdict authority. See the in-app [Limitations](/limitations), [Privacy](/privacy), and [How it works](/how-it-works) pages.

## Architecture and operational limits

- `frontend/`: Next.js, React, and TypeScript. The browser API origin defaults to `http://localhost:8000`; set `NEXT_PUBLIC_API_URL` for another origin.
- `backend/`: FastAPI. `POST /api/analyze` validates an image and queues analysis; `GET /api/analyze/{job_id}/events` streams the in-process job events.
- Video API: `GET /api/video/config` reports processing limits and whether FFmpeg/ffprobe are present; `POST /api/video/analyze` accepts supported video, `GET /api/video/analyze/{job_id}/events` streams real job events, and `GET /api/video/result/{token}` returns the persisted summary.
- Result summaries, traces, and feedback reports are stored in `data/results.db`. The temporary image file is removed after analysis. There is no configured retention/deletion policy.
- Active analysis jobs and their event streams are held in process memory for up to an hour. Use one API worker for the supplied local setup; multi-worker deployments need shared job/event coordination.
- Video decoding requires `ffmpeg` and `ffprobe` on the backend PATH. The Docker API image installs FFmpeg. Codec support is verified by actual decoding of sampled frames and depends on the installed FFmpeg build.
- `/api/samples` currently returns no assets. `/api/insights` returns aggregate metrics and is disabled unless `INSIGHTS_ACCESS_TOKEN` is configured.
- C2PA checks are performed only if the `c2patool` executable is installed and available on `PATH`.
- The offline PWA page is available without a network connection; image analysis still requires the backend.

## Local setup

Use Python 3.12 for the pinned dependency set and Node.js 20.9 or newer. For local video analysis, install an FFmpeg distribution that includes both `ffmpeg` and `ffprobe`, add them to PATH, then open a new terminal and verify:

```powershell
Get-Command ffmpeg, ffprobe
```

The development environment used to produce this release did not have those executables installed. The video decoder path therefore requires real-media verification on a configured machine.

### Backend terminal (PowerShell, project root)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn backend.main:app --reload --port 8000
```

Health check: <http://localhost:8000/health>

### Frontend terminal

```powershell
Set-Location frontend
npm ci
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
npm run dev
```

Open <http://localhost:3000>.

## Environment configuration

Backend settings are read from the root `.env` file:

| Variable | Purpose |
|---|---|
| `MAX_IMAGE_BYTES` | Maximum image request size in bytes; default `10485760` (10 MiB). |
| `MAX_IMAGE_PIXELS` | Maximum decoded image pixels; default `10000000`. |
| `VIDEO_MAX_SIZE_MB` | Maximum video size; default `100` MiB. |
| `VIDEO_MAX_DURATION_SECONDS` | Maximum duration; default `600` seconds (10 minutes). |
| `VIDEO_MAX_RESOLUTION_WIDTH`, `VIDEO_MAX_RESOLUTION_HEIGHT` | Maximum video resolution, accepting portrait or landscape orientation; defaults `1920` and `1080`. |
| `VIDEO_MAX_FPS` | Maximum reported frame rate; default `60`. |
| `MAX_ANALYZED_FRAMES` | Hard frame-inference budget per video; default `24`. |
| `FRAME_SAMPLE_INTERVAL_SECONDS` | Target interval used to determine the uniform sampling budget; default `5`. |
| `VIDEO_SCENE_SAMPLE_INTERVAL_SECONDS`, `VIDEO_SCENE_THRESHOLD` | Low-resolution scene-scan interval and FFmpeg scene-change threshold; defaults `2` seconds and `0.30`. |
| `VIDEO_ANALYSIS_TIMEOUT_SECONDS` | Overall FFmpeg/decode/detector budget; default `300` seconds. |
| `MAX_FACE_TRACKS` | Reserved face-track budget. No face detection/tracking implementation is currently configured; default `0`. |
| `DETECTOR_A_MODEL`, `DETECTOR_A_AI_LABEL` | Model ID and exact AI-class label verified from that model's documentation. |
| `DETECTOR_B_MODEL`, `DETECTOR_B_AI_LABEL` | A second, different model ID and its exact AI-class label. |
| `DETECTOR_C_MODEL`, `DETECTOR_C_AI_LABEL` | Optional third distinct model and exact AI-class label. |
| `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | Optional provider credentials, API origin, and model ID. The project does not claim a verified Nemotron model ID. |
| `VISION_MODEL` | Optional vision model. If configured and called, the uploaded image is sent to the configured provider. |
| `INSIGHTS_ACCESS_TOKEN` | Optional server-side bearer token; without it, aggregate insights are disabled. |
| `NEXT_PUBLIC_API_URL` | Frontend build/runtime API origin; configure in the frontend environment. |

Do not put provider credentials in `NEXT_PUBLIC_*` variables or commit `.env`. Verify the model cards, exact label names, endpoint, and provider terms yourself; the repository intentionally does not invent or endorse model IDs.

### Optional C2PA verification

Install a compatible `c2patool` executable separately and ensure it is on the backend process `PATH`. It is not included in `requirements.txt` or the Docker image, and its installation/runtime behavior has not been verified in this workspace. Without it, C2PA is reported as not verifiable.

## Tests and benchmark

Backend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Frontend checks:

```powershell
Set-Location frontend
npm run lint
npm run build
```

End-to-end smoke test (start the backend in another terminal first):

```powershell
Set-Location frontend
npx playwright install chromium
npm run test:e2e
```

The smoke test submits a real small PNG to the local backend when available. It does not mock analysis or treat a test fixture as a valid forensic conclusion. Without the backend it checks the user-facing unavailable state.

For a benchmark, supply appropriately licensed labeled images in `benchmark/real/`, `benchmark/ai/`, `benchmark/real_compressed/`, and `benchmark/ai_compressed/`, configure two distinct detectors and their verified AI labels, then run from the repository root:

```powershell
.\.venv\Scripts\python.exe benchmark\evaluate.py
```

The script runs the configured pipeline on each valid supported image and writes aggregate measurements to `benchmark/results.md`; filenames and image contents are not copied to the report. Inconclusive results count as incorrect in overall accuracy and are also reported separately. No images or measured results are included here, and the script does not create calibration data. See [benchmark instructions](benchmark/README.md) and [sample-asset policy](frontend/public/samples/README.md).

## Docker

Copy `.env.example` to `.env`, then from the project root run:

```powershell
docker compose up --build
```

The compose file starts the API and frontend and persists SQLite data in a named volume. Set `NEXT_PUBLIC_API_URL` in `.env` before building if the browser must use an API origin other than `http://localhost:8000`. The API image installs FFmpeg. Docker is not installed in the development environment used for this release, so image build and container behavior are not verified here.

## Remaining unverified

- No user-supplied benchmark images/videos, benchmark measurements, or calibration artifact are present.
- No detector model IDs, exact model labels, Hugging Face inference downloads, live provider credentials, or verified Nebius/Nemotron model ID have been configured and exercised.
- Optional C2PA verification depends on a separately installed `c2patool`.
- Real MP4, MOV, and WebM decode behavior, codec coverage, limits, scene sampling, and end-to-end video analysis were not exercised because FFmpeg/ffprobe and user-provided video fixtures were unavailable.
- Face tracking and audio authenticity analysis are not implemented. The language model does not select video tools; it only drafts an explanation from already-computed evidence when configured.
- The `benchmark/video/` labeled folder structure is reserved for future video evaluation; no video benchmark runner or measured results are included.
- Production Docker build/deployment, PWA install prompts across browsers, and production retention/access-control behavior require validation in the target environment.
- Public feature claims should remain conservative until representative labeled data and independent operational testing exist.

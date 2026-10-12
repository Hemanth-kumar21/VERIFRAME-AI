# Veriframe AI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js&logoColor=white)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![NVIDIA Nemotron](https://img.shields.io/badge/NVIDIA-Nemotron--3-76B900?logo=nvidia&logoColor=white)](https://build.nvidia.com)
[![Nebius Token Factory](https://img.shields.io/badge/Nebius-Token%20Factory-0052FF)](https://nebius.com)

**Veriframe AI** is an evidence-led media forensics and authenticity verification platform for synthetic image and deepfake video detection. It combines deterministic forensic signal analysis with **NVIDIA Nemotron multimodal reasoning**, accelerated by **Nebius Token Factory**.

- **Public Repository URL:** [https://github.com/Hemanth-kumar21/VERY-FRAME-AI](https://github.com/Hemanth-kumar21/VERY-FRAME-AI)
- **License:** [MIT License (OSI Approved)](LICENSE)

---

## 🌟 Highlights: NVIDIA Nemotron & Nebius Token Factory

### 1. NVIDIA Nemotron Multimodal Reasoning (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` & `nvidia/nemotron-3-super-120b-a12b`)

Veriframe AI integrates NVIDIA open-source Nemotron models to perform deep semantic reasoning over extracted video frames:

- **Multimodal Video Comprehension:** Videos are sampled using uniform intervals and scene-change detection (`FFmpeg`). Representative chronological keyframes are converted to base64 data URIs and passed directly into **NVIDIA Nemotron-3-Nano-Omni**.
- **Structured Temporal Evidence:** Nemotron reconstructs the narrative timeline, produces timestamped event logs, detects camera and subject movements, and identifies synthetic temporal inconsistencies across frames.
- **Reasoning Budget Allocation:** Requests configure `reasoning_budget=1024` for internal Chain-of-Thought reflection, ensuring rigorous scrutiny before synthesizing findings into structured JSON.
- **Evidence-Grounded Forensic Q&A ("Ask Nemotron"):** Investigators and judges can query the video in natural language. Answers are strictly constrained to the observed frame evidence, citing exact timestamps and explicitly flagging when visual evidence is insufficient.

### 2. Nebius Token Factory Acceleration

**Nebius Token Factory** serves as the high-performance AI inference engine powering Veriframe AI's LLM workflows:

- **High-Throughput & Low-Latency Streaming:** Token Factory’s OpenAI-compatible endpoint (`https://api.tokenfactory.nebius.com/v1`) delivers near-zero latency token generation, allowing real-time forensic reporting without GPU bottlenecks.
- **Zero-Infrastructure Scale:** Enabled deploying and testing massive 100B+ open models (such as Nemotron Super and Nano Omni) instantly without provisioning or managing physical GPU clusters.
- **Dynamic Endpoint Verification & Tool Calling:** `backend/check_llm.py` connects at runtime to the Nebius Token Factory `/v1/models` registry to verify active model weights and test tool-calling capabilities dynamically.
- **Rapid Prototyping:** Drastically accelerated development cycles by enabling continuous prompt tuning and integration testing with fast turnaround times.

---

## 🏗️ Architecture Overview

```
                                  Client Browser
                         (Next.js 16 UI / Playwright E2E)
                                       │
                                       ▼
                       Reverse Proxy (Caddy / Ports 80 & 443)
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
             Frontend Container                     Backend API
             (Next.js App Router)               (FastAPI / PyTorch)
                    │                                     │
                    │                    ┌────────────────┼────────────────┐
                    │                    ▼                ▼                ▼
                    │             FFmpeg Decoder    Deterministic    SQLite DB
                    │            (Scene Sampling)   Forensic Engines (results.db)
                    │                                     │
                    └─────────────────────────────────────┼────────────────┘
                                                          │
                                         ┌────────────────┴────────────────┐
                                         ▼                                 ▼
                             NVIDIA Nemotron Models              Nebius Token Factory
                         (Multimodal Video Intelligence)     (High-Speed LLM Inference)
```

---

## 🚀 Setup & Quick Start

### Prerequisites
- **Python 3.12+**
- **Node.js 20.9+** & **npm**
- **FFmpeg & ffprobe** (required for video decoding; included in the Docker image)
- *(Optional)* **Docker & Docker Compose**

---

### Option A: Local Development (Recommended)

#### 1. Clone the Repository
```bash
git clone https://github.com/Hemanth-kumar21/VERIFRAME-AI.git
cd VERIFRAME-AI
```

#### 2. Backend Setup (PowerShell / Terminal 1)
```powershell
# Create and activate Python virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1   # On Linux/macOS: source .venv/bin/activate

# Install dependencies
python -m pip install -r requirements.txt

# Configure environment
Copy-Item .env.example .env

# Run FastAPI backend
uvicorn backend.main:app --reload --port 8000
```
Health Check: [http://localhost:8000/health](http://localhost:8000/health)

#### 3. Frontend Setup (Terminal 2)
```powershell
cd frontend
npm ci
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

### Option B: Docker Compose (All-in-One)

Build and run both frontend, backend, and reverse proxy in isolated containers:

```bash
cp .env.example .env
docker compose up --build
```
Access the application at [http://localhost:3000](http://localhost:3000).

---

### Option C: One-Click Startup Script (Windows PowerShell)

```powershell
.\start_app.ps1
```

---

## ⚙️ Environment Configuration

Configuration values are loaded from the root `.env` file:

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `NVIDIA_API_KEY` | API Key for NVIDIA Nemotron / Nebius Token Factory | `nvapi-...` |
| `NVIDIA_BASE_URL` | Endpoint for Nemotron multimodal completions | `https://integrate.api.nvidia.com/v1/chat/completions` |
| `NVIDIA_MODEL` | Nemotron model identifier | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| `LLM_BASE_URL` | Nebius Token Factory endpoint | `https://api.tokenfactory.nebius.com/v1` |
| `LLM_MODEL` | Text reasoning model ID | `nvidia/nemotron-3-super-120b-a12b` |
| `DEMO_DETECTORS` | Enable local demo edge & entropy forensic detectors | `true` |
| `VIDEO_MAX_SIZE_MB`| Maximum supported video upload size | `100` |
| `MAX_ANALYZED_FRAMES` | Maximum frames sampled per video | `24` |
| `VIDEO_SCENE_THRESHOLD` | Sensitivity threshold for scene change extraction | `0.30` |
| `NEXT_PUBLIC_API_URL` | Backend URL used by Next.js frontend | `http://localhost:8000` |

---

## 🧪 Testing & Verification

### Backend Unit & Integration Tests
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
Runs tests covering image validation, tile analysis, forensic correlation, C2PA checking, and the NVIDIA Nemotron client.

### Frontend Quality & Type Checks
```powershell
cd frontend
npm run lint
npm run build
```

### End-to-End Playwright Tests
```powershell
cd frontend
npx playwright install chromium
npm run test:e2e
```

### Forensic Benchmarking Suite
To run benchmark evaluations against labeled real and synthetic media:
```powershell
.\.venv\Scripts\python.exe benchmark\evaluate.py
```
Detailed instructions are available in [benchmark/README.md](benchmark/README.md).

---

## 📄 License

This project is licensed under the **MIT License** — an approved Open Source Initiative (OSI) license. See the [LICENSE](LICENSE) file for details.

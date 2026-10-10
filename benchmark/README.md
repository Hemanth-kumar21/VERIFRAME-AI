# Benchmarking Very Frame AI

This runner evaluates actual backend verdicts against locally supplied labels. No images or results are bundled with this repository.

## Supply labeled media

Create these folders and place only images you are permitted to use in them:

- `real/`
- `ai/`
- `real_compressed/`
- `ai_compressed/`

Treat `real` and `real_compressed` as the non-AI label; treat `ai` and `ai_compressed` as the AI label. Keep the source and labeling method for every asset documented outside any public report. The runner supports the same PNG, JPEG, and WEBP types accepted by the backend. Unsupported files and invalid images are counted and skipped.

## Configure detectors

Before evaluation, configure at least two distinct Hugging Face image-classification model IDs and the exact AI-class labels returned by those models in the root `.env`. Inspect the model cards, licensing, label mappings, and suitability yourself. No detector IDs or labels are supplied as verified by this project.

## Run

From the repository root:

```powershell
.\.venv\Scripts\python.exe benchmark\evaluate.py
```

The runner validates each image using backend validation and calls the configured image-analysis pipeline with the optional LLM disabled. It writes aggregate measurements (not filenames or image content) to `benchmark/results.md`. Inconclusive results count as incorrect in overall accuracy; conclusive accuracy and coverage are reported separately. The false-positive rate denominator is all valid labeled real images, with inconclusive results not counted as false positives.

No report is generated if folders are missing, fewer than two distinct configured models are available, or there are no valid images. If detectors cannot load or fail at inference, the resulting inconclusive outcomes will affect the measurements; review backend traces/logs and do not interpret the aggregate as proof of general model accuracy.

## Calibration warning

A benchmark report is not calibration. The runner does not emit calibrated confidence intervals, operating thresholds, or calibration artifacts. Results describe only the supplied dataset and current configuration; they are not generalizable accuracy claims.

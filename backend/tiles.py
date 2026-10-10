from __future__ import annotations

from PIL import Image

from .detectors import run_detector_ensemble


def run_tile_analysis(image_path: str) -> dict:
    with Image.open(image_path) as opened:
        image = opened.convert("RGB")
    width, height = image.size
    step_x = max(1, width // 4)
    step_y = max(1, height // 4)
    tiles = []
    try:
        for y in range(0, height, step_y):
            for x in range(0, width, step_x):
                bounds = (x, y, min(width, x + step_x * 2), min(height, y + step_y * 2))
                crop = image.crop(bounds)
                try:
                    result = run_detector_ensemble(crop)
                finally:
                    crop.close()
                signal = result["average"] if result["status"] == "ok" else None
                tiles.append(
                    {
                        "x": x,
                        "y": y,
                        "signal": signal,
                        "status": result["status"],
                    }
                )
                if len(tiles) >= 20:
                    break
            if len(tiles) >= 20:
                break
    finally:
        image.close()

    valid_signals = [tile["signal"] for tile in tiles if tile["signal"] is not None]
    return {
        "label": "Areas where configured detector signals are stronger. Not proof of editing.",
        "experimental": True,
        "status": "ok" if valid_signals else "not_configured",
        "tiles": tiles,
        "heat_score": round(sum(valid_signals) / len(valid_signals), 2) if valid_signals else None,
    }

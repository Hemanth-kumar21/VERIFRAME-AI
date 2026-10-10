from __future__ import annotations

import io
import textwrap

from PIL import Image, ImageDraw, ImageFont


def create_share_card(result: dict, result_url: str) -> bytes:
    image = Image.new("RGB", (1200, 630), "#07111f")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.rounded_rectangle((42, 42, 1158, 588), radius=30, fill="#10243a", outline="#2e5b78", width=2)
    summaries = result.get("tool_summaries")
    is_video = isinstance(summaries, dict) and isinstance(summaries.get("video"), dict)
    media_label = "VIDEO" if is_video else "IMAGE"
    draw.text((88, 88), f"VERY FRAME AI  |  {media_label} EVIDENCE REVIEW", fill="#7dd3fc", font=font)
    draw.text((88, 160), "VERDICT", fill="#aab8c9", font=font)
    draw.text((88, 205), str(result.get("verdict", "Inconclusive"))[:80], fill="#ffffff", font=font)

    translations = result.get("explanation")
    translated_explanation = translations.get("en") if isinstance(translations, dict) else None
    explanation = str(
        result.get("plain_explanation")
        or translated_explanation
        or "The evidence is not sufficient for a clear conclusion."
    )
    y = 280
    for line in textwrap.wrap(explanation, width=105)[:3]:
        draw.text((88, y), line, fill="#d7e5f2", font=font)
        y += 27

    draw.text((88, 425), "Estimate, not proof. Verify the original source independently.", fill="#fbbf24", font=font)
    draw.text((88, 480), result_url[:135], fill="#7dd3fc", font=font)
    media_kind = "video" if is_video else "image"
    draw.text((88, 535), f"The original uploaded {media_kind} is not included in this card.", fill="#aab8c9", font=font)

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    image.close()
    return output.getvalue()

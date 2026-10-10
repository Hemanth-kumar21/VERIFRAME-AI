from __future__ import annotations


UNSUPPORTED_PATTERNS = [
    "proof",
    "definitely",
    "certainly",
    "authentic",
    "real photo",
]


def review_grounding(tool_outputs: dict, draft_explanation: str) -> dict:
    lower = draft_explanation.lower()
    unsupported_claims = []
    for phrase in UNSUPPORTED_PATTERNS:
        if phrase in lower:
            unsupported_claims.append(f"Claim uses unsupported wording: '{phrase}'")

    if len(unsupported_claims) == 0 and not tool_outputs:
        unsupported_claims.append("No tool output was supplied.")

    return {
        "supported": not unsupported_claims,
        "unsupported_claims": unsupported_claims,
    }

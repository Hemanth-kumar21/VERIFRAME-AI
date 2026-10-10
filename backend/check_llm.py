from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()


def check_llm_status() -> dict[str, Any]:
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")
    api_key = os.getenv("LLM_API_KEY")

    if not base_url or not model:
        return {
            "available": False,
            "status": "missing_config",
            "message": "LLM_BASE_URL or LLM_MODEL is not configured.",
            "tool_calling": "not_checked",
        }
    if not api_key:
        return {
            "available": False,
            "status": "missing_key",
            "message": "LLM_API_KEY is missing. The app continues in deterministic fallback mode.",
            "tool_calling": "not_checked",
        }

    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/models", headers=headers, timeout=10)
    except httpx.RequestError:
        return {
            "available": False,
            "status": "network_error",
            "message": "Network error while checking the LLM provider.",
            "tool_calling": "not_checked",
        }

    if response.status_code in {401, 403}:
        return {
            "available": False,
            "status": "invalid_key",
            "message": "The provider rejected the configured API key.",
            "tool_calling": "not_checked",
        }
    if response.status_code >= 400:
        return {
            "available": False,
            "status": "provider_error",
            "message": f"LLM provider responded with status {response.status_code}.",
            "tool_calling": "not_checked",
        }

    try:
        payload = response.json()
        model_entries = payload.get("data")
        if not isinstance(model_entries, list):
            raise ValueError("Model list is not an array.")
        model_ids = [
            item.get("id") or item.get("model")
            for item in model_entries
            if isinstance(item, dict)
        ]
    except (ValueError, TypeError, AttributeError):
        return {
            "available": False,
            "status": "invalid_model_list",
            "message": "The provider returned an invalid model list.",
            "tool_calling": "not_checked",
        }

    listed = model in model_ids
    tool_calling = "not_checked"
    tool_error = None
    if listed:
        tool_calling = "unsupported"
        tool_payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Call the get_file_info tool now."}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_file_info",
                        "description": "Connectivity check; do not request or return user files.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False,
                        },
                    },
                }
            ],
            "tool_choice": {
                "type": "function",
                "function": {"name": "get_file_info"},
            },
        }
        try:
            tool_response = httpx.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=tool_payload,
                timeout=15,
            )
            if tool_response.status_code in {401, 403}:
                return {
                    "available": False,
                    "status": "invalid_key",
                    "message": "The provider rejected the configured API key during tool-call verification.",
                    "model_listed": True,
                    "tool_calling": "not_checked",
                }
            if tool_response.status_code == 200:
                tool_payload_response = tool_response.json()
                choice = tool_payload_response["choices"][0]
                tool_calls = choice["message"].get("tool_calls", [])
                if any(
                    call.get("function", {}).get("name") == "get_file_info"
                    for call in tool_calls
                ):
                    tool_calling = "supported"
            else:
                tool_error = f"Tool-call verification returned HTTP {tool_response.status_code}."
        except httpx.RequestError:
            tool_error = "Network error during tool-call verification."
        except (ValueError, KeyError, IndexError, TypeError):
            tool_error = "The provider returned an invalid tool-call response."

    status = "online" if listed else "model_unavailable"
    message = f"Configured model listed: {listed}. Tool calling: {tool_calling}."
    if tool_error:
        message = f"Configured model listed: {listed}. {tool_error}"
    return {
        "available": listed,
        "status": status,
        "message": message,
        "model_listed": listed,
        "tool_calling": tool_calling,
    }


def main() -> None:
    status = check_llm_status()
    print(f"LLM_BASE_URL={os.getenv('LLM_BASE_URL')}")
    print(f"LLM_MODEL={os.getenv('LLM_MODEL')}")
    print(status["message"])


if __name__ == "__main__":
    main()

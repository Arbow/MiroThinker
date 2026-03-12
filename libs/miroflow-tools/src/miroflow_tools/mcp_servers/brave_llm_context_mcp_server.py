# Copyright (c) 2025 MiroMind
# This source code is licensed under the Apache 2.0 License.

"""Brave Search LLM Context MCP server.

This server wraps Brave Search's LLM Context endpoint:
https://api-dashboard.search.brave.com/api-reference/summarizer/llm_context/post

It returns structured grounding snippets optimized for agent / LLM consumption.
"""

import json
import os
from typing import Any

import requests
from fastmcp import FastMCP
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .utils import decode_http_urls_in_dict

BRAVE_LLM_CONTEXT_URL = "https://api.search.brave.com/res/v1/llm/context"

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
BRAVE_API_VERSION = os.getenv("BRAVE_API_VERSION", "")

mcp = FastMCP("brave-llm-context-mcp-server")


def _is_banned_url(url: str) -> bool:
    if not url:
        return False
    banned_list = [
        "unifuncs",
        "huggingface.co/datasets",
        "huggingface.co/spaces",
    ]
    return any(banned in url for banned in banned_list)


def _normalize_country(country: str) -> str:
    value = (country or "").strip()
    if not value:
        return "us"
    return value.lower()


def _normalize_search_lang(search_lang: str) -> str:
    value = (search_lang or "").strip().lower()
    if not value:
        return "en"

    # Brave is strict about Chinese language variants in practice.
    if value in {"zh", "zh-cn", "zh-sg", "zh-my"}:
        return "zh-hans"
    if value in {"zh-tw", "zh-hk", "zh-mo"}:
        return "zh-hant"
    if value.startswith("zh-") and ("hans" in value):
        return "zh-hans"
    if value.startswith("zh-") and ("hant" in value):
        return "zh-hant"

    return value


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(
        (requests.ConnectionError, requests.Timeout, requests.HTTPError)
    ),
)
def _post_llm_context(
    payload: dict[str, Any], headers: dict[str, str]
) -> requests.Response:
    response = requests.post(
        BRAVE_LLM_CONTEXT_URL,
        json=payload,
        headers=headers,
        timeout=30,
    )
    # Retry only on rate limiting / transient server errors.
    if response.status_code == 429 or response.status_code >= 500:
        response.raise_for_status()
    return response


@mcp.tool()
def brave_llm_context(
    q: str,
    country: str = "US",
    search_lang: str = "en",
    count: int = 10,
    maximum_number_of_tokens: int = 8192,
    maximum_number_of_urls: int = 10,
    maximum_number_of_tokens_per_url: int = 4096,
    context_threshold_mode: str = "balanced",
    freshness: str | None = None,
    goggles: str | None = None,
) -> str:
    """Fetch Brave "LLM Context" grounding snippets for a query.

    Args:
        q: Search query.
        country: Country code (e.g., "US").
        search_lang: Search language (e.g., "en").
        count: Number of results to consider (1-50).
        maximum_number_of_tokens: Total token budget for returned context.
        maximum_number_of_urls: Max number of URLs included in context.
        maximum_number_of_tokens_per_url: Per-URL token budget.
        context_threshold_mode: strict|balanced|lenient|disabled.
        freshness: Time filter: pd|pw|pm|py|YYYY-MM-DDtoYYYY-MM-DD.
        goggles: Optional Brave "goggles" filter string.

    Returns:
        JSON string containing Brave's response with `grounding` and `sources`.
    """
    if not BRAVE_API_KEY:
        return json.dumps(
            {
                "success": False,
                "error": "BRAVE_API_KEY environment variable not set",
                "grounding": {"generic": []},
                "sources": {},
            },
            ensure_ascii=False,
        )

    if not q or not q.strip():
        return json.dumps(
            {
                "success": False,
                "error": "Search query 'q' is required and cannot be empty",
                "grounding": {"generic": []},
                "sources": {},
            },
            ensure_ascii=False,
        )

    payload: dict[str, Any] = {
        "q": q.strip(),
        "country": _normalize_country(country),
        "search_lang": _normalize_search_lang(search_lang),
        "count": count,
        "maximum_number_of_tokens": maximum_number_of_tokens,
        "maximum_number_of_urls": maximum_number_of_urls,
        "maximum_number_of_tokens_per_url": maximum_number_of_tokens_per_url,
        "context_threshold_mode": context_threshold_mode,
    }

    if freshness:
        payload["freshness"] = freshness
    if goggles:
        payload["goggles"] = goggles

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json",
        "X-Subscription-Token": BRAVE_API_KEY,
    }
    if BRAVE_API_VERSION:
        headers["Api-Version"] = BRAVE_API_VERSION

    try:
        response = _post_llm_context(payload, headers)

        if response.status_code != 200:
            body_text = response.text or ""
            body_preview = body_text[:2000]
            try:
                error_obj = response.json()
            except Exception:
                error_obj = None

            error_detail = None
            meta_errors = None
            if isinstance(error_obj, dict):
                err = error_obj.get("error")
                if isinstance(err, dict):
                    error_detail = err.get("detail") or err.get("message")
                    meta = err.get("meta")
                    if isinstance(meta, dict):
                        meta_errors = meta.get("errors")

            return json.dumps(
                {
                    "success": False,
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code} from Brave LLM context endpoint",
                    "error_detail": error_detail,
                    "meta_errors": meta_errors,
                    "body_preview": body_preview,
                    "grounding": {"generic": []},
                    "sources": {},
                },
                ensure_ascii=False,
            )

        try:
            data = response.json()
        except Exception:
            body_preview = (response.text or "")[:2000]
            return json.dumps(
                {
                    "success": False,
                    "error": "Failed to parse JSON response from Brave",
                    "body_preview": body_preview,
                    "grounding": {"generic": []},
                    "sources": {},
                },
                ensure_ascii=False,
            )

        # Best-effort filtering to avoid evaluation leakage sources.
        grounding = data.get("grounding")
        if isinstance(grounding, dict) and isinstance(grounding.get("generic"), list):
            grounding["generic"] = [
                item
                for item in grounding["generic"]
                if not _is_banned_url((item or {}).get("url", ""))
            ]

        data = decode_http_urls_in_dict(data)
        return json.dumps(data, ensure_ascii=False)
    except requests.HTTPError as e:
        status_code = getattr(getattr(e, "response", None), "status_code", None)
        body_preview = getattr(getattr(e, "response", None), "text", "") or ""
        return json.dumps(
            {
                "success": False,
                "status_code": status_code,
                "error": f"HTTP error calling Brave: {str(e)}",
                "body_preview": body_preview[:2000],
                "grounding": {"generic": []},
                "sources": {},
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "grounding": {"generic": []},
                "sources": {},
            },
            ensure_ascii=False,
        )


if __name__ == "__main__":
    mcp.run()

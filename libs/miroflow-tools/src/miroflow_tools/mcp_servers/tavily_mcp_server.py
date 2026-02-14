# Copyright (c) 2025 MiroMind
# This source code is licensed under the MIT License.

"""
Tavily MCP Server for MiroThinker
High-quality search API optimized for AI agents
"""

import json
import os
from typing import Any, Dict, Optional

import httpx
from mcp.server.fastmcp import FastMCP
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Tavily Configuration
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_BASE_URL = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com")

# Initialize FastMCP server
mcp = FastMCP("tavily-mcp-server")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(
        (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)
    ),
)
async def make_tavily_request(
    endpoint: str,
    payload: Dict[str, Any],
    timeout: float = 60.0,
) -> httpx.Response:
    """Make HTTP request to Tavily API with retry logic."""
    headers = {
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{TAVILY_BASE_URL}/{endpoint}",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        return response


@mcp.tool()
async def tavily_search(
    q: str,
    search_depth: str = "basic",
    include_answer: bool = True,
    include_raw_content: bool = False,
    max_results: int = 10,
    include_domains: Optional[list[str]] = None,
    exclude_domains: Optional[list[str]] = None,
    include_images: bool = False,
    topic: str = "general",
    days: Optional[int] = None,
):
    """
    Tool to perform web searches via Tavily API - optimized for AI agents.

    Tavily provides high-quality search results with AI-generated answers and optional 
    raw content extraction. It's specifically designed for AI agent use cases.

    Args:
        q: Search query string (required)
        search_depth: Search depth - 'basic' (fast) or 'advanced' (comprehensive, slower)
        include_answer: Include AI-generated answer summary (default: True)
        include_raw_content: Include raw HTML content of search results (default: False)
        max_results: Maximum number of results (default: 10, max: 100)
        include_domains: List of domains to specifically include (e.g., ['arxiv.org', 'github.com'])
        exclude_domains: List of domains to exclude
        include_images: Include image search results (default: False)
        topic: Topic type - 'general' or 'news' (news enables time-based filtering)
        days: Number of days back to search (only for news topic, max: 30)

    Returns:
        Dictionary containing search results, AI-generated answer, and metadata.
    """
    # Check for API key
    if not TAVILY_API_KEY:
        return json.dumps(
            {
                "success": False,
                "error": "TAVILY_API_KEY environment variable not set",
                "results": [],
            },
            ensure_ascii=False,
        )

    # Validate required parameter
    if not q or not q.strip():
        return json.dumps(
            {
                "success": False,
                "error": "Search query 'q' is required and cannot be empty",
                "results": [],
            },
            ensure_ascii=False,
        )

    # Validate search_depth
    if search_depth not in ["basic", "advanced"]:
        return json.dumps(
            {
                "success": False,
                "error": f"Invalid search_depth: {search_depth}. Must be 'basic' or 'advanced'",
                "results": [],
            },
            ensure_ascii=False,
        )

    # Validate max_results
    if max_results < 1 or max_results > 100:
        return json.dumps(
            {
                "success": False,
                "error": f"Invalid max_results: {max_results}. Must be between 1 and 100",
                "results": [],
            },
            ensure_ascii=False,
        )

    # Validate topic
    if topic not in ["general", "news"]:
        return json.dumps(
            {
                "success": False,
                "error": f"Invalid topic: {topic}. Must be 'general' or 'news'",
                "results": [],
            },
            ensure_ascii=False,
        )

    try:
        # Build payload
        payload: dict[str, Any] = {
            "api_key": TAVILY_API_KEY,
            "query": q.strip(),
            "search_depth": search_depth,
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
            "max_results": max_results,
            "include_images": include_images,
            "topic": topic,
        }

        # Add optional parameters
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains
        if days is not None and topic == "news":
            payload["days"] = min(days, 30)  # Max 30 days

        # Make the API request
        response = await make_tavily_request("search", payload)
        data = response.json()

        # Check for error
        if "error" in data:
            return json.dumps(
                {
                    "success": False,
                    "error": data["error"],
                    "results": [],
                },
                ensure_ascii=False,
            )

        # Format response to match Serper-like structure for compatibility
        results = data.get("results", [])
        
        organic_results = []
        for item in results:
            organic_result = {
                "title": item.get("title", ""),
                "link": item.get("url", ""),
                "snippet": item.get("content", ""),
                "score": item.get("score", 0),
            }
            
            # Include raw content if available
            if include_raw_content and "raw_content" in item:
                organic_result["raw_content"] = item["raw_content"]
                
            organic_results.append(organic_result)

        # Build response
        response_data = {
            "success": True,
            "organic": organic_results,
            "query": data.get("query", q.strip()),
            "search_depth": search_depth,
            "total_results": len(organic_results),
        }

        # Include AI-generated answer if available
        if include_answer and "answer" in data:
            response_data["answer"] = data["answer"]
            response_data["ai_answer"] = data["answer"]  # Alias for compatibility

        # Include images if requested
        if include_images and "images" in data:
            response_data["images"] = data["images"]

        # Include follow-up questions if available
        if "follow_up_questions" in data:
            response_data["follow_up_questions"] = data["follow_up_questions"]

        return json.dumps(response_data, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error: {e.response.status_code}"
        try:
            error_data = e.response.json()
            if "error" in error_data:
                error_msg = f"Tavily API error: {error_data['error']}"
        except:
            error_body = e.response.text
            if error_body:
                error_msg = f"Tavily API error: {error_body[:200]}"
        
        return json.dumps(
            {"success": False, "error": error_msg, "results": []},
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps(
            {"success": False, "error": f"Unexpected error: {str(e)}", "results": []},
            ensure_ascii=False,
        )


@mcp.tool()
async def tavily_extract(
    urls: list[str],
    extract_depth: str = "basic",
    include_images: bool = False,
):
    """
    Tool to extract content from specific URLs using Tavily Extract API.

    This tool extracts structured content from web pages, including raw content, 
    images, and metadata. It's useful when you need to read the full content of 
    specific pages found in search results.

    Args:
        urls: List of URLs to extract content from (required, max: 20)
        extract_depth: Extraction depth - 'basic' or 'advanced' (default: 'basic')
        include_images: Whether to include images in the extraction (default: False)

    Returns:
        Dictionary containing extracted content from each URL.
    """
    # Check for API key
    if not TAVILY_API_KEY:
        return json.dumps(
            {
                "success": False,
                "error": "TAVILY_API_KEY environment variable not set",
            },
            ensure_ascii=False,
        )

    # Validate URLs
    if not urls or len(urls) == 0:
        return json.dumps(
            {"success": False, "error": "At least one URL is required"},
            ensure_ascii=False,
        )

    if len(urls) > 20:
        return json.dumps(
            {"success": False, "error": "Maximum 20 URLs allowed per request"},
            ensure_ascii=False,
        )

    # Validate extract_depth
    if extract_depth not in ["basic", "advanced"]:
        return json.dumps(
            {
                "success": False,
                "error": f"Invalid extract_depth: {extract_depth}. Must be 'basic' or 'advanced'",
            },
            ensure_ascii=False,
        )

    try:
        # Build payload
        payload: dict[str, Any] = {
            "api_key": TAVILY_API_KEY,
            "urls": urls,
            "extract_depth": extract_depth,
            "include_images": include_images,
        }

        # Make the API request
        response = await make_tavily_request("extract", payload, timeout=120.0)
        data = response.json()

        # Check for error
        if "error" in data:
            return json.dumps(
                {
                    "success": False,
                    "error": data["error"],
                },
                ensure_ascii=False,
            )

        # Format results
        results = data.get("results", [])
        failed_urls = data.get("failed_urls", [])

        extracted_data = []
        for result in results:
            extracted_item = {
                "url": result.get("url", ""),
                "raw_content": result.get("raw_content", ""),
                "images": result.get("images", []) if include_images else [],
            }
            extracted_data.append(extracted_item)

        response_data = {
            "success": True,
            "extracted_data": extracted_data,
            "failed_urls": failed_urls,
            "total_extracted": len(extracted_data),
            "total_failed": len(failed_urls),
        }

        return json.dumps(response_data, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error: {e.response.status_code}"
        try:
            error_data = e.response.json()
            if "error" in error_data:
                error_msg = f"Tavily API error: {error_data['error']}"
        except:
            pass
        
        return json.dumps(
            {"success": False, "error": error_msg},
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps(
            {"success": False, "error": f"Unexpected error: {str(e)}"},
            ensure_ascii=False,
        )


if __name__ == "__main__":
    mcp.run()

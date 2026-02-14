# Copyright (c) 2025 MiroMind
# This source code is licensed under the MIT License.

"""
Firecrawl MCP Server for MiroThinker
Supports both search and scrape functionality via Firecrawl API
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

# Firecrawl Configuration
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
FIRECRAWL_BASE_URL = os.getenv("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev/v1")

# Initialize FastMCP server
mcp = FastMCP("firecrawl-mcp-server")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(
        (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)
    ),
)
async def make_firecrawl_request(
    endpoint: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    timeout: float = 60.0,
) -> httpx.Response:
    """Make HTTP request to Firecrawl API with retry logic."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{FIRECRAWL_BASE_URL}/{endpoint}",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        return response


@mcp.tool()
async def firecrawl_search(
    q: str,
    limit: int = 10,
    lang: str = "en",
    country: str = "us",
    scrape_options: Optional[Dict[str, Any]] = None,
):
    """
    Tool to perform web searches via Firecrawl API and retrieve search results with optional content scraping.

    Firecrawl search provides high-quality search results with the ability to scrape content from result pages.
    It supports filtering by language, country, and can extract clean markdown content from pages.

    Args:
        q: Search query string (required)
        limit: Number of results to return (default: 10, max: 100)
        lang: Language code for search results (e.g., 'en', 'zh', 'ja')
        country: Country code for search results (e.g., 'us', 'cn', 'jp')
        scrape_options: Optional dict with scraping configuration:
            - formats: List of formats to extract (['markdown', 'html', 'screenshot'])
            - only_main_content: Whether to extract only main content (default: True)
            - include_tags: List of HTML tags to include
            - exclude_tags: List of HTML tags to exclude

    Returns:
        Dictionary containing search results with metadata and optionally scraped content.
    """
    # Check for API key
    if not FIRECRAWL_API_KEY:
        return json.dumps(
            {
                "success": False,
                "error": "FIRECRAWL_API_KEY environment variable not set",
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

    # Validate limit
    if limit < 1 or limit > 100:
        return json.dumps(
            {
                "success": False,
                "error": f"Invalid limit: {limit}. Must be between 1 and 100",
                "results": [],
            },
            ensure_ascii=False,
        )

    try:
        # Build payload
        payload: dict[str, Any] = {
            "query": q.strip(),
            "limit": limit,
            "lang": lang,
            "country": country,
        }

        # Add scrape options if provided
        if scrape_options:
            payload["scrapeOptions"] = scrape_options

        # Set up headers
        headers = {
            "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
            "Content-Type": "application/json",
        }

        # Make the API request to search endpoint
        response = await make_firecrawl_request("search", payload, headers)
        data = response.json()

        # Check for success
        if not data.get("success"):
            return json.dumps(
                {
                    "success": False,
                    "error": data.get("error", "Unknown error from Firecrawl API"),
                    "results": [],
                },
                ensure_ascii=False,
            )

        # Format response to match Serper-like structure
        search_results = data.get("data", [])
        
        # Convert to organic results format (compatible with existing agent code)
        organic_results = []
        for item in search_results:
            organic_results.append({
                "title": item.get("title", ""),
                "link": item.get("url", ""),
                "snippet": item.get("description", ""),
                "markdown": item.get("markdown", ""),  # Firecrawl provides this
                "html": item.get("html", ""),
            })

        response_data = {
            "success": True,
            "organic": organic_results,
            "searchParameters": {
                "q": q.strip(),
                "limit": limit,
                "lang": lang,
                "country": country,
            },
            "totalResults": len(organic_results),
        }

        return json.dumps(response_data, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error: {e.response.status_code}"
        try:
            error_data = e.response.json()
            if "error" in error_data:
                error_msg = f"Firecrawl API error: {error_data['error']}"
        except:
            pass
        
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
async def firecrawl_scrape(
    url: str,
    formats: list[str] = None,
    only_main_content: bool = True,
    include_tags: Optional[list[str]] = None,
    exclude_tags: Optional[list[str]] = None,
    headers: Optional[Dict[str, str]] = None,
    wait_for: Optional[int] = None,
    timeout: int = 30000,
):
    """
    Tool to scrape and extract content from a specific URL using Firecrawl.

    This tool can extract clean markdown, HTML, screenshots, and other formats from any web page.
    It's useful when you need to read the full content of a specific page found in search results.

    Args:
        url: The URL to scrape (required)
        formats: List of formats to extract (default: ['markdown'])
            Options: 'markdown', 'html', 'screenshot', 'links', 'metadata'
        only_main_content: Whether to extract only the main content (default: True)
        include_tags: List of HTML tags to specifically include
        exclude_tags: List of HTML tags to exclude
        headers: Custom HTTP headers to use when scraping
        wait_for: Time in milliseconds to wait for page to load
        timeout: Request timeout in milliseconds (default: 30000)

    Returns:
        Dictionary containing scraped content in requested formats.
    """
    # Check for API key
    if not FIRECRAWL_API_KEY:
        return json.dumps(
            {
                "success": False,
                "error": "FIRECRAWL_API_KEY environment variable not set",
            },
            ensure_ascii=False,
        )

    # Validate URL
    if not url or not url.strip():
        return json.dumps(
            {"success": False, "error": "URL is required and cannot be empty"},
            ensure_ascii=False,
        )

    # Default formats
    if formats is None:
        formats = ["markdown"]

    try:
        # Build payload
        payload: dict[str, Any] = {
            "url": url.strip(),
            "formats": formats,
            "onlyMainContent": only_main_content,
            "timeout": timeout,
        }

        # Add optional parameters
        if include_tags:
            payload["includeTags"] = include_tags
        if exclude_tags:
            payload["excludeTags"] = exclude_tags
        if headers:
            payload["headers"] = headers
        if wait_for:
            payload["waitFor"] = wait_for

        # Set up headers
        request_headers = {
            "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
            "Content-Type": "application/json",
        }

        # Make the API request to scrape endpoint
        response = await make_firecrawl_request(
            "scrape", payload, request_headers, timeout=timeout / 1000 + 10
        )
        data = response.json()

        # Check for success
        if not data.get("success"):
            return json.dumps(
                {
                    "success": False,
                    "error": data.get("error", "Unknown error from Firecrawl API"),
                },
                ensure_ascii=False,
            )

        # Extract data
        scrape_data = data.get("data", {})
        
        response_data = {
            "success": True,
            "url": url.strip(),
            "markdown": scrape_data.get("markdown", ""),
            "html": scrape_data.get("html", ""),
            "metadata": scrape_data.get("metadata", {}),
            "links": scrape_data.get("links", []),
        }

        # Add screenshot if requested
        if "screenshot" in formats:
            response_data["screenshot"] = scrape_data.get("screenshot", "")

        return json.dumps(response_data, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error: {e.response.status_code}"
        try:
            error_data = e.response.json()
            if "error" in error_data:
                error_msg = f"Firecrawl API error: {error_data['error']}"
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

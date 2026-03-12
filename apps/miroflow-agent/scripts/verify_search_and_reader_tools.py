# Copyright (c) 2025 MiroMind
# This source code is licensed under the Apache 2.0 License.

"""Verify external search/reader tools without touching git-tracked secrets.

This script validates:
1) Brave Search LLM Context tool (local stdio MCP server)
2) Zhipu/BigModel WebReader MCP (remote streamableHttp MCP server)

Keys are read from environment variables only.

Run from `apps/miroflow-agent/`:

  uv run python scripts/verify_search_and_reader_tools.py

Environment variables:
  - BRAVE_API_KEY
  - (optional) BRAVE_API_VERSION
  - BIGMODEL_API_KEY
  - (optional) BIGMODEL_WEB_READER_MCP_URL
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any

from omegaconf import OmegaConf

from miroflow_tools.manager import ToolManager

from src.config.settings import create_mcp_server_parameters


def _json_loads_maybe(text: str) -> Any:
    try:
        value: Any = json.loads(text)
        # Some MCP servers return JSON as a JSON-encoded string (double-encoded).
        if isinstance(value, str):
            stripped = value.lstrip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    return json.loads(value)
                except Exception:
                    return value
        return value
    except Exception:
        return None


async def _verify_brave(query: str) -> int:
    if not (os.environ.get("BRAVE_API_KEY") or "").strip():
        print("[brave] missing env var: BRAVE_API_KEY")
        return 2

    cfg = OmegaConf.create({})
    agent_cfg = OmegaConf.create(
        {"tools": ["tool-brave-llm-context"], "tool_blacklist": []}
    )
    server_configs, blacklist = create_mcp_server_parameters(cfg, agent_cfg)
    tool_manager = ToolManager(server_configs, tool_blacklist=blacklist)

    tools = await tool_manager.get_all_tool_definitions()
    brave_tools = next(
        (s for s in tools if s.get("name") == "tool-brave-llm-context"), None
    )
    tool_names = [
        t.get("name")
        for t in (brave_tools or {}).get("tools", [])
        if isinstance(t, dict)
    ]
    print(f"[brave] tools: {tool_names}")

    result = await tool_manager.execute_tool_call(
        server_name="tool-brave-llm-context",
        tool_name="brave_llm_context",
        arguments={"q": query, "count": 8, "maximum_number_of_tokens": 4096},
    )
    if "error" in result:
        print(f"[brave] error: {result['error']}")
        return 1

    payload = _json_loads_maybe(result.get("result", ""))
    if not isinstance(payload, dict):
        print("[brave] unexpected non-JSON response")
        print((result.get("result") or "")[:300])
        return 1

    grounding = payload.get("grounding") or {}
    generic = grounding.get("generic") or []
    print(f"[brave] grounding.generic items: {len(generic)}")

    for item in generic[:2]:
        if not isinstance(item, dict):
            continue
        print(f"[brave] - {item.get('title')} | {item.get('url')}")
    return 0


async def _verify_zhipu_web_reader(url: str) -> int:
    if not (os.environ.get("BIGMODEL_API_KEY") or "").strip():
        print("[zhipu] missing env var: BIGMODEL_API_KEY")
        return 2

    cfg = OmegaConf.create({})
    agent_cfg = OmegaConf.create({"tools": ["zhipu_web_reader"], "tool_blacklist": []})
    server_configs, blacklist = create_mcp_server_parameters(cfg, agent_cfg)
    tool_manager = ToolManager(server_configs, tool_blacklist=blacklist)

    tools = await tool_manager.get_all_tool_definitions()
    zhipu_tools = next((s for s in tools if s.get("name") == "zhipu_web_reader"), None)
    tool_names = [
        t.get("name")
        for t in (zhipu_tools or {}).get("tools", [])
        if isinstance(t, dict)
    ]
    print(f"[zhipu] tools: {tool_names}")

    # Most docs refer to tool name `webReader`.
    tool_name = (
        "webReader"
        if "webReader" in tool_names
        else (tool_names[0] if tool_names else "webReader")
    )
    result = await tool_manager.execute_tool_call(
        server_name="zhipu_web_reader",
        tool_name=tool_name,
        arguments={"url": url},
    )
    if "error" in result:
        print(f"[zhipu] error: {result['error']}")
        return 1

    text = result.get("result", "") or ""
    payload = _json_loads_maybe(text)
    if isinstance(payload, dict):
        reader_result = payload.get("reader_result") or payload.get("data") or payload
        title = (
            reader_result.get("title") if isinstance(reader_result, dict) else None
        ) or ""
        content = (
            reader_result.get("content") if isinstance(reader_result, dict) else None
        ) or ""
        print(f"[zhipu] title: {title[:120]}")
        print(f"[zhipu] content length: {len(content)}")
        if content:
            print("[zhipu] content preview:")
            print(content[:300])
    else:
        print("[zhipu] non-JSON result preview:")
        print(text[:500])

    return 0


async def _amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["brave", "zhipu", "all"], default="all")
    parser.add_argument("--brave-query", default="Brave Search LLM context API")
    parser.add_argument("--url", default="https://example.com")
    args = parser.parse_args()

    rc = 0
    if args.only in {"brave", "all"}:
        rc = max(rc, await _verify_brave(args.brave_query))
    if args.only in {"zhipu", "all"}:
        rc = max(rc, await _verify_zhipu_web_reader(args.url))
    return rc


def main() -> None:
    raise SystemExit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()

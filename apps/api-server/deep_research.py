# Copyright (c) 2025 MiroMind
# This source code is licensed under the MIT License.

"""
MiroThinker Deep Research Runner
Runs MiroThinker agent for multi-turn deep research

This module provides deep research functionality using the real MiroThinker Agent
with Hydra configuration and Tavily MCP server.
"""

import os
from typing import Dict, Any

# API Configuration
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_BASE_URL = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com")

SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
SILICONFLOW_MODEL = os.getenv("SILICONFLOW_MODEL", "Pro/zai-org/GLM-5")

JINA_API_KEY = os.getenv("JINA_API_KEY", "")
JINA_BASE_URL = os.getenv("JINA_BASE_URL", "https://r.jina.ai")

# Import MiroThinker Agent (requires optional dependencies)
try:
    from mirothinker_agent import MiroThinkerAgent
except ImportError as e:
    raise RuntimeError(
        "MiroThinker Agent not available. "
        "Install dependencies: uv sync --extra mirothinker"
    ) from e


async def run_deep_research(
    query: str,
    max_turns: int = 20,
) -> Dict[str, Any]:
    """
    Run deep research using real MiroThinker Agent with MCP
    
    This uses the actual MiroThinker Agent with:
    - Hydra configuration
    - Tavily MCP server
    - Jina MCP server (for web scraping with LLM summary)
    - Multi-turn tool calls
    - Real Agent reasoning
    
    The max_turns parameter controls how many tool calls the Agent can make.
    Each turn represents one search or analysis step.
    
    Args:
        query: Research topic or question
        max_turns: Maximum number of Agent tool calls (1-50, default 20)
    
    Returns:
        Dict with success status, final_answer, task_id, log_file, etc.
    """
    if not TAVILY_API_KEY:
        raise ValueError("TAVILY_API_KEY not configured")
    
    if not SILICONFLOW_API_KEY:
        raise ValueError("SILICONFLOW_API_KEY not configured")
    
    if not JINA_API_KEY:
        raise ValueError("JINA_API_KEY not configured")
    
    # Initialize MiroThinker Agent
    agent = MiroThinkerAgent(
        tavily_api_key=TAVILY_API_KEY,
        siliconflow_api_key=SILICONFLOW_API_KEY,
        siliconflow_base_url=SILICONFLOW_BASE_URL,
        siliconflow_model=SILICONFLOW_MODEL,
        jina_api_key=JINA_API_KEY,
        jina_base_url=JINA_BASE_URL,
        max_turns=max_turns,
        agent_config="tavily_official",
    )
    
    # Run research
    result = await agent.research(query)
    
    # Format output
    return {
        "success": result.get("success", False),
        "query": query,
        "search_rounds": max_turns,
        "final_answer": result.get("final_answer", result.get("thinking_process", "")),
        "task_id": result.get("task_id"),
        "log_file": result.get("log_file"),
    }
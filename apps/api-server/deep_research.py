# Copyright (c) 2025 MiroMind
# This source code is licensed under the MIT License.

"""
MiroThinker Deep Research Runner
Runs MiroThinker agent for multi-turn deep research
"""

import asyncio
import os
import subprocess
import tempfile
import json
from pathlib import Path
from typing import Optional, Dict, Any
import httpx

# Configuration
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
SILICONFLOW_MODEL = os.getenv("SILICONFLOW_MODEL", "Pro/zai-org/GLM-5")

MIROFLOW_AGENT_DIR = Path(__file__).parent.parent / "miroflow-agent"


async def run_deep_research(
    query: str,
    max_turns: int = 50,
    llm_config: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Run MiroThinker deep research using Tavily MCP
    
    This function:
    1. Sets up MiroThinker configuration
    2. Runs the agent with the query
    3. Captures the output
    4. Returns structured results
    """
    
    # Default LLM config
    if llm_config is None:
        llm_config = {
            "base_url": SILICONFLOW_BASE_URL,
            "api_key": SILICONFLOW_API_KEY,
            "model": SILICONFLOW_MODEL,
        }
    
    # Create a temporary config file for this research task
    config_content = f"""defaults:
  - default
  - _self_

main_agent:
  tools:
    - tool-python
    - tavily-mcp
  max_turns: {max_turns}
  system_prompt: |
    You are MiroThinker, an expert deep research agent. Your goal is to thoroughly research the user's query.
    
    Instructions:
    1. Break down complex queries into sub-questions
    2. Use tavily_search to gather information from multiple sources
    3. Analyze and synthesize the information
    4. Provide a comprehensive, well-structured report
    5. Cite your sources
    
    Always use the search tool to verify facts. Don't rely on your training data alone.

mcp_servers:
  tavily-mcp:
    command: npx
    args: ["-y", "tavily-mcp@latest"]
    env:
      TAVILY_API_KEY: {os.getenv('TAVILY_API_KEY', '')}
"""
    
    # Write temporary config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        # Prepare environment
        env = os.environ.copy()
        env['PYTHONPATH'] = str(MIROFLOW_AGENT_DIR.parent)
        
        # Build command to run MiroThinker
        # Note: This is a simplified version. In production, you'd want to:
        # 1. Use the MiroFlow library directly instead of subprocess
        # 2. Stream output in real-time
        # 3. Handle interactive prompts properly
        
        cmd = [
            "python", "-m", "miroflow_agent.main",
            f"--config-path={config_path}",
            f"query={query}",
            f"llm.base_url={llm_config['base_url']}",
            f"llm.api_key={llm_config['api_key']}",
            f"llm.model={llm_config['model']}",
        ]
        
        # For now, return a placeholder
        # Real implementation would run the subprocess and capture output
        return {
            "success": False,
            "error": "Deep research runner requires MiroThinker CLI integration. "
                     "Please run MiroThinker directly: "
                     f"cd {MIROFLOW_AGENT_DIR} && uv run python main.py agent=tavily_official ...",
            "query": query,
        }
        
    finally:
        # Cleanup
        os.unlink(config_path)


async def run_simple_research(
    query: str,
    max_search_rounds: int = 3,
) -> Dict[str, Any]:
    """
    Simple multi-round research using direct API calls
    
    This is a lightweight alternative to full MiroThinker integration.
    It performs multiple Tavily searches iteratively.
    """
    
    from main import call_tavily_search, call_siliconflow_llm
    
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
    
    if not TAVILY_API_KEY:
        raise ValueError("TAVILY_API_KEY not configured")
    
    search_history = []
    current_query = query
    
    for round_num in range(max_search_rounds):
        print(f"[Research Round {round_num + 1}/{max_search_rounds}] Query: {current_query}")
        
        # Search
        search_result = await call_tavily_search(
            query=current_query,
            search_depth="advanced",
            max_results=10,
            include_answer=True,
        )
        
        search_history.append({
            "round": round_num + 1,
            "query": current_query,
            "results": search_result.get("results", []),
            "answer": search_result.get("answer", ""),
        })
        
        # If we have an answer, we might be done
        if search_result.get("answer") and round_num >= 1:
            break
        
        # Otherwise, generate follow-up questions
        if SILICONFLOW_API_KEY and round_num < max_search_rounds - 1:
            context = "\n\n".join([
                f"Title: {r.get('title', '')}\n{r.get('content', '')[:500]}"
                for r in search_result.get("results", [])[:5]
            ])
            
            follow_up_prompt = f"""Based on these search results about "{query}", what additional information do we need to find? 

Search results:
{context}

Suggest a specific follow-up search query that would help answer the main question more completely. 
Respond with ONLY the follow-up query, nothing else."""
            
            try:
                current_query = await call_siliconflow_llm(
                    "You are a research assistant.",
                    follow_up_prompt,
                    temperature=0.7,
                    max_tokens=200
                )
                current_query = current_query.strip().strip('"')
            except Exception as e:
                print(f"Failed to generate follow-up: {e}")
                break
    
    # Generate final report from all search rounds
    all_context = []
    for sh in search_history:
        for r in sh["results"][:3]:
            all_context.append(f"Source: {r.get('title')}\n{r.get('content', '')[:800]}")
    
    context_str = "\n\n".join(all_context[:15])  # Top 15 sources
    
    final_prompt = f"""Based on the following research gathered from multiple search rounds, provide a comprehensive report.

Original Question: {query}

Research Sources:
{context_str}

Provide a detailed report with:
1. Executive Summary
2. Key Findings (with specific details)
3. Analysis and Insights
4. Conclusions

Format with clear headings and bullet points."""
    
    final_answer = await call_siliconflow_llm(
        "You are an expert research analyst. Provide comprehensive, well-structured reports.",
        final_prompt,
        temperature=0.3,
        max_tokens=8192
    )
    
    return {
        "success": True,
        "query": query,
        "search_rounds": len(search_history),
        "final_answer": final_answer,
        "search_history": [
            {"round": sh["round"], "query": sh["query"], "result_count": len(sh["results"])}
            for sh in search_history
        ],
    }

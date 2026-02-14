# Copyright (c) 2025 MiroMind
# This source code is licensed under the MIT License.

"""
MiroThinker Deep Research Runner
Runs MiroThinker agent for multi-turn deep research
"""

import asyncio
import os
import httpx
from typing import Optional, Dict, Any

# API Configuration
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_BASE_URL = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com")

SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
SILICONFLOW_MODEL = os.getenv("SILICONFLOW_MODEL", "Pro/zai-org/GLM-5")

# Try to import MiroThinker Agent (requires optional dependencies)
mirothinker_available = False
try:
    from mirothinker_agent import MiroThinkerAgent
    mirothinker_available = True
except ImportError:
    MiroThinkerAgent = None
    print("⚠️  MiroThinker Agent not available. Install with: uv sync --extra mirothinker")


async def run_mirothinker_deep_research(
    query: str,
    max_turns: int = 20,
) -> Dict[str, Any]:
    """
    Run deep research using real MiroThinker Agent with MCP
    
    This uses the actual MiroThinker Agent with:
    - Hydra configuration
    - Tavily MCP server
    - Multi-turn tool calls
    - Real Agent reasoning
    """
    if not mirothinker_available:
        raise RuntimeError(
            "MiroThinker Agent not available. "
            "Install dependencies: uv sync --extra mirothinker"
        )
    
    if not TAVILY_API_KEY:
        raise ValueError("TAVILY_API_KEY not configured")
    
    if not SILICONFLOW_API_KEY:
        raise ValueError("SILICONFLOW_API_KEY not configured")
    
    # Initialize MiroThinker Agent
    agent = MiroThinkerAgent(
        tavily_api_key=TAVILY_API_KEY,
        siliconflow_api_key=SILICONFLOW_API_KEY,
        siliconflow_base_url=SILICONFLOW_BASE_URL,
        siliconflow_model=SILICONFLOW_MODEL,
        max_turns=max_turns,
        agent_config="tavily_official",
    )
    
    # Run research
    result = await agent.research(query)
    
    # Format to match simple research output
    return {
        "success": result.get("success", False),
        "query": query,
        "search_rounds": max_turns,  # Agent runs up to max_turns
        "final_answer": result.get("final_answer", result.get("thinking_process", "")),
        "search_history": [],  # Agent doesn't provide per-round history in this format
        "is_mirothinker": True,
        "task_id": result.get("task_id"),
        "log_file": result.get("log_file"),
    }


async def call_tavily_search(
    query: str,
    search_depth: str = "basic",
    max_results: int = 10,
    include_answer: bool = True,
    include_raw_content: bool = False,
    topic: str = "general",
    days: Optional[int] = None,
) -> Dict[str, Any]:
    """Call Tavily search API"""
    
    if not TAVILY_API_KEY:
        raise ValueError("TAVILY_API_KEY not configured")
    
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": search_depth,
        "include_answer": include_answer,
        "include_raw_content": include_raw_content,
        "max_results": max_results,
        "topic": topic,
    }
    
    if days is not None and topic == "news":
        payload["days"] = min(days, 30)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{TAVILY_BASE_URL}/search",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()


async def call_siliconflow_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 8192,
) -> str:
    """Call SiliconFlow LLM API (GLM-5)"""
    
    if not SILICONFLOW_API_KEY:
        raise ValueError("SILICONFLOW_API_KEY not configured")
    
    payload = {
        "model": SILICONFLOW_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{SILICONFLOW_BASE_URL}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def run_simple_research(
    query: str,
    max_search_rounds: int = 3,
) -> Dict[str, Any]:
    """
    Simple multi-round research using direct API calls
    
    This is a lightweight alternative to full MiroThinker integration.
    It performs multiple Tavily searches iteratively.
    """
    
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
        
        # Only break early if we have a comprehensive answer AND reached near max rounds
        # Don't break early just because Tavily returned an answer - continue for depth
        if search_result.get("answer") and round_num >= max_search_rounds - 1:
            break
        
        # Always generate follow-up questions until max rounds reached
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

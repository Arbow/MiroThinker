# Copyright (c) 2025 MiroMind
# This source code is licensed under the MIT License.

"""
MiroThinker HTTP API Server
Simple blocking API for search tasks using Tavily
"""

import asyncio
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Add miroflow-agent to Python path
MIROFLOW_AGENT_DIR = Path(__file__).parent / ".." / "miroflow-agent"
sys.path.insert(0, str(MIROFLOW_AGENT_DIR))

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# API Configuration
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_BASE_URL = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com")

JINA_API_KEY = os.getenv("JINA_API_KEY", "")
JINA_BASE_URL = os.getenv("JINA_BASE_URL", "https://r.jina.ai")

SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
SILICONFLOW_MODEL = os.getenv("SILICONFLOW_MODEL", "Pro/zai-org/GLM-5")

# Task storage (in-memory, use Redis in production)
task_store: Dict[str, Dict[str, Any]] = {}


class SearchRequest(BaseModel):
    """Search request model"""
    query: str = Field(..., description="Search query", min_length=1, max_length=1000)
    search_depth: str = Field(default="basic", description="Search depth: basic or advanced")
    max_results: int = Field(default=10, ge=1, le=100)
    include_answer: bool = Field(default=True, description="Include AI-generated answer")
    include_raw_content: bool = Field(default=False, description="Include raw page content")
    topic: str = Field(default="general", description="Topic: general or news")
    days: Optional[int] = Field(default=None, description="For news, days back to search")
    force_llm_answer: bool = Field(default=True, description="Force use LLM to generate detailed answer based on all search results")


class SearchResponse(BaseModel):
    """Search response model"""
    task_id: str
    status: str
    query: str
    created_at: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class TaskStatusResponse(BaseModel):
    """Task status response model"""
    task_id: str
    status: str  # pending, running, completed, failed
    query: str
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print("🚀 Starting MiroThinker HTTP API Server")
    print(f"📡 Tavily Base URL: {TAVILY_BASE_URL}")
    print(f"🤖 SiliconFlow Model: {SILICONFLOW_MODEL}")
    
    if not TAVILY_API_KEY:
        print("⚠️  Warning: TAVILY_API_KEY not set")
    if not SILICONFLOW_API_KEY:
        print("⚠️  Warning: SILICONFLOW_API_KEY not set")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down API Server")


app = FastAPI(
    title="MiroThinker HTTP API",
    description="Simple blocking API for AI search using Tavily",
    version="1.0.0",
    lifespan=lifespan,
)


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


async def call_jina_scrape(url: str) -> str:
    """Call Jina AI to scrape and summarize webpage"""
    
    if not JINA_API_KEY:
        raise ValueError("JINA_API_KEY not configured")
    
    headers = {
        "Authorization": f"Bearer {JINA_API_KEY}",
        "Accept": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{JINA_BASE_URL}/{url}",
            headers=headers,
        )
        response.raise_for_status()
        return response.text


async def call_siliconflow_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
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


async def execute_search_task(task_id: str, request: SearchRequest):
    """Execute search task"""
    
    task_store[task_id]["status"] = "running"
    
    try:
        # 1. Call Tavily search
        print(f"[{task_id}] Searching: {request.query}")
        
        search_result = await call_tavily_search(
            query=request.query,
            search_depth=request.search_depth,
            max_results=request.max_results,
            include_answer=request.include_answer,
            include_raw_content=request.include_raw_content,
            topic=request.topic,
            days=request.days,
        )
        
        # 2. Generate AI answer using GLM-5 for detailed analysis
        ai_answer = search_result.get("answer", "")
        
        if SILICONFLOW_API_KEY and (request.force_llm_answer or not ai_answer):
            print(f"[{task_id}] Generating detailed AI answer with GLM-5")
            
            # Build comprehensive context from search results
            organic_results = search_result.get("results", [])
            context_parts = []
            for i, r in enumerate(organic_results[:8], 1):
                title = r.get('title', 'No title')
                content = r.get('content', '')[:800]  # Increased context length
                url = r.get('url', '')
                context_parts.append(f"[{i}] {title}\nURL: {url}\nContent: {content}\n")
            
            context = "\n".join(context_parts)
            
            system_prompt = """You are an expert research analyst. Your task is to provide a comprehensive, detailed answer based on the provided search results. 

Requirements:
1. Analyze all provided search results thoroughly
2. Structure your answer with clear sections and bullet points
3. Include specific data, numbers, and facts from the sources
4. Cite sources using [1], [2], etc. when referencing information
5. If the search results contain conflicting information, acknowledge it
6. Provide actionable insights and conclusions
7. Answer in the same language as the user's query
8. Be thorough - this is a deep research report, not a brief summary"""
            
            user_prompt = f"""Research Query: {request.query}

Search Results:
{context}

Please provide a comprehensive research report answering the query. Include:
- Key findings and main points
- Specific data and evidence from sources
- Analysis and insights
- Conclusions and recommendations

Format your response with clear headings and bullet points for readability."""
            
            try:
                ai_answer = await call_siliconflow_llm(
                    system_prompt, 
                    user_prompt,
                    temperature=0.3,
                    max_tokens=8192  # GLM-5 supports up to 192K context
                )
                print(f"[{task_id}] LLM answer generated successfully ({len(ai_answer)} chars)")
            except Exception as e:
                print(f"[{task_id}] Failed to generate AI answer: {e}")
                if not ai_answer:  # Only use Tavily answer if LLM failed and no Tavily answer
                    ai_answer = "Error generating detailed answer. Using search results only."
        
        # 3. Build final result
        result = {
            "query": request.query,
            "search_depth": request.search_depth,
            "topic": request.topic,
            "results": search_result.get("results", []),
            "ai_answer": ai_answer,
            "total_results": len(search_result.get("results", [])),
        }
        
        # Include images if available
        if "images" in search_result:
            result["images"] = search_result["images"]
        
        task_store[task_id].update({
            "status": "completed",
            "result": result,
            "completed_at": datetime.now().isoformat(),
        })
        
        print(f"[{task_id}] Search completed successfully")
        
    except Exception as e:
        error_msg = str(e)
        print(f"[{task_id}] Search failed: {error_msg}")
        task_store[task_id].update({
            "status": "failed",
            "error": error_msg,
            "completed_at": datetime.now().isoformat(),
        })


@app.post("/api/search", response_model=SearchResponse)
async def create_search_task(
    request: SearchRequest,
    background_tasks: BackgroundTasks,
):
    """
    Create a new search task.
    
    This endpoint creates a search task and returns immediately with task_id.
    Use GET /api/search/{task_id} to poll for results.
    """
    
    # Validate API keys
    if not TAVILY_API_KEY:
        raise HTTPException(status_code=500, detail="TAVILY_API_KEY not configured")
    
    task_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    
    # Store task
    task_store[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "query": request.query,
        "created_at": created_at,
        "result": None,
        "error": None,
        "completed_at": None,
    }
    
    # Execute in background
    background_tasks.add_task(execute_search_task, task_id, request)
    
    return SearchResponse(
        task_id=task_id,
        status="pending",
        query=request.query,
        created_at=created_at,
    )


@app.post("/api/search/sync")
async def search_sync(request: SearchRequest):
    """
    Synchronous search (blocking until complete).
    
    This endpoint waits for the search to complete before returning.
    Suitable for simple use cases where you need immediate results.
    """
    
    if not TAVILY_API_KEY:
        raise HTTPException(status_code=500, detail="TAVILY_API_KEY not configured")
    
    try:
        # Call Tavily search directly
        search_result = await call_tavily_search(
            query=request.query,
            search_depth=request.search_depth,
            max_results=request.max_results,
            include_answer=request.include_answer,
            include_raw_content=request.include_raw_content,
            topic=request.topic,
            days=request.days,
        )
        
        # Generate detailed AI answer using GLM-5
        ai_answer = search_result.get("answer", "")
        
        if SILICONFLOW_API_KEY and (request.force_llm_answer or not ai_answer):
            organic_results = search_result.get("results", [])
            context_parts = []
            for i, r in enumerate(organic_results[:8], 1):
                title = r.get('title', 'No title')
                content = r.get('content', '')[:800]
                url = r.get('url', '')
                context_parts.append(f"[{i}] {title}\nURL: {url}\nContent: {content}\n")
            
            context = "\n".join(context_parts)
            
            system_prompt = """You are an expert research analyst. Your task is to provide a comprehensive, detailed answer based on the provided search results. 

Requirements:
1. Analyze all provided search results thoroughly
2. Structure your answer with clear sections and bullet points
3. Include specific data, numbers, and facts from the sources
4. Cite sources using [1], [2], etc. when referencing information
5. If the search results contain conflicting information, acknowledge it
6. Provide actionable insights and conclusions
7. Answer in the same language as the user's query
8. Be thorough - this is a deep research report, not a brief summary"""
            
            user_prompt = f"""Research Query: {request.query}

Search Results:
{context}

Please provide a comprehensive research report answering the query. Include:
- Key findings and main points
- Specific data and evidence from sources
- Analysis and insights
- Conclusions and recommendations

Format your response with clear headings and bullet points for readability."""
            
            try:
                ai_answer = await call_siliconflow_llm(
                    system_prompt,
                    user_prompt,
                    temperature=0.3,
                    max_tokens=8192  # GLM-5 supports up to 192K context
                )
            except Exception as e:
                print(f"Failed to generate AI answer: {e}")
                if not ai_answer:
                    ai_answer = "Error generating detailed answer."
        
        return {
            "success": True,
            "query": request.query,
            "results": search_result.get("results", []),
            "ai_answer": ai_answer,
            "total_results": len(search_result.get("results", [])),
        }
        
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Tavily API error: {e.response.text}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from deep_research import run_simple_research

class DeepResearchRequest(BaseModel):
    """Deep research request model"""
    query: str = Field(..., description="Research query", min_length=1, max_length=2000)
    max_search_rounds: int = Field(default=3, ge=1, le=10, description="Maximum number of search rounds")


# Try to import MiroThinker agent (requires optional dependencies)
mirothinker_available = False
try:
    from mirothinker_agent import run_mirothinker_research
    mirothinker_available = True
except ImportError:
    run_mirothinker_research = None
    print("⚠️  MiroThinker agent not available. Install with: uv sync --extra mirothinker")


class MiroThinkerRequest(BaseModel):
    """MiroThinker agent request model"""
    query: str = Field(..., description="Research query for MiroThinker agent", min_length=1, max_length=2000)
    max_turns: int = Field(default=50, ge=1, le=100, description="Maximum agent turns")


@app.post("/api/mirothinker/research")
async def mirothinker_research(request: MiroThinkerRequest):
    """
    Run MiroThinker Agent for deep research.
    
    This endpoint uses the actual MiroThinker agent with Tavily MCP,
    performing multi-turn tool-augmented reasoning.
    
    **This is the true MiroThinker deep research experience.**
    """
    if not mirothinker_available:
        raise HTTPException(
            status_code=503,
            detail="MiroThinker agent not available. Install dependencies: uv sync --extra mirothinker"
        )
    
    try:
        result = await run_mirothinker_research(
            query=request.query,
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500, 
                detail=result.get("error", "Unknown error")
            )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/deep-research")
async def deep_research(request: DeepResearchRequest):
    """
    Multi-round deep research.
    
    Performs iterative searches and synthesis, similar to MiroThinker's approach.
    Uses Tavily for search and GLM-5 for analysis.
    """
    if not TAVILY_API_KEY:
        raise HTTPException(status_code=500, detail="TAVILY_API_KEY not configured")
    
    try:
        result = await run_simple_research(
            query=request.query,
            max_search_rounds=request.max_search_rounds,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Get search task status and results.
    
    Poll this endpoint to check if a search task is complete.
    """
    
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = task_store[task_id]
    
    return TaskStatusResponse(
        task_id=task_id,
        status=task["status"],
        query=task["query"],
        created_at=task["created_at"],
        completed_at=task.get("completed_at"),
        result=task.get("result"),
        error=task.get("error"),
    )


@app.get("/api/scrape")
async def scrape_url(url: str):
    """
    Scrape content from a URL using Jina AI.
    
    Query parameter:
    - url: URL to scrape (required)
    """
    if not JINA_API_KEY:
        raise HTTPException(status_code=500, detail="JINA_API_KEY not configured")
    
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")
    
    try:
        content = await call_jina_scrape(url)
        return {
            "success": True,
            "url": url,
            "content": content,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "tavily_configured": bool(TAVILY_API_KEY),
        "jina_configured": bool(JINA_API_KEY),
        "siliconflow_configured": bool(SILICONFLOW_API_KEY),
        "active_tasks": len([t for t in task_store.values() if t["status"] == "running"]),
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "MiroThinker HTTP API",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/search": "Create async search task",
            "POST /api/search/sync": "Synchronous search (blocking)",
            "GET /api/search/{task_id}": "Get task status/results",
            "GET /api/scrape": "Scrape URL content (Jina)",
            "GET /api/health": "Health check",
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8080))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(app, host=host, port=port)

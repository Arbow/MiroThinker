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
        
        # 2. If no AI answer from Tavily, generate one using GLM-5
        ai_answer = search_result.get("answer", "")
        
        if not ai_answer and SILICONFLOW_API_KEY:
            print(f"[{task_id}] Generating AI answer with GLM-5")
            
            # Build context from search results
            organic_results = search_result.get("results", [])
            context = "\n\n".join([
                f"Title: {r.get('title', '')}\nContent: {r.get('content', '')[:500]}"
                for r in organic_results[:5]
            ])
            
            system_prompt = """You are a helpful research assistant. Based on the provided search results, 
provide a comprehensive answer to the user's question. Cite sources when possible."""
            
            user_prompt = f"""Question: {request.query}

Search Results:
{context}

Please provide a comprehensive answer based on these search results."""
            
            try:
                ai_answer = await call_siliconflow_llm(system_prompt, user_prompt)
            except Exception as e:
                print(f"[{task_id}] Failed to generate AI answer: {e}")
                ai_answer = ""
        
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
        
        # Generate AI answer if needed
        ai_answer = search_result.get("answer", "")
        
        if not ai_answer and SILICONFLOW_API_KEY:
            organic_results = search_result.get("results", [])
            context = "\n\n".join([
                f"Title: {r.get('title', '')}\nContent: {r.get('content', '')[:500]}"
                for r in organic_results[:5]
            ])
            
            try:
                ai_answer = await call_siliconflow_llm(
                    "You are a helpful research assistant.",
                    f"Question: {request.query}\n\nSearch Results:\n{context}\n\nProvide a comprehensive answer."
                )
            except Exception as e:
                print(f"Failed to generate AI answer: {e}")
        
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

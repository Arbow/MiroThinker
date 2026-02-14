# MiroThinker HTTP API

Simple HTTP API for AI search using Tavily and SiliconFlow GLM-5.

## Features

- 🔍 **Tavily Search**: High-quality web search optimized for AI agents
- 🤖 **GLM-5 Integration**: AI answer generation using SiliconFlow
- ⚡ **Simple API**: RESTful endpoints with blocking and async modes
- 📊 **Health Monitoring**: Health check endpoint for monitoring

## Quick Start

### 1. Configure API Keys

```bash
cd apps/api-server
cp .env.example .env
# Edit .env with your actual API keys
```

### 2. Install Dependencies

**Using uv (recommended - fast, no package conflicts):**
```bash
uv sync
```

**Or using conda:**
```bash
conda create -n mirothinker-api python=3.10
conda activate mirothinker-api
pip install fastapi uvicorn httpx pydantic python-dotenv
```

### 3. Start Server

```bash
./start.sh
# Or directly
uv run python main.py
```

Server will start at `http://localhost:8080`

## API Endpoints

### POST `/api/search` - Async Search

Create a search task and get task_id. Poll GET `/api/search/{task_id}` for results.

**Request:**
```json
{
  "query": "What is the latest AI research?",
  "search_depth": "basic",
  "max_results": 10,
  "include_answer": true,
  "include_raw_content": false,
  "topic": "general"
}
```

**Response:**
```json
{
  "task_id": "uuid",
  "status": "pending",
  "query": "What is the latest AI research?",
  "created_at": "2026-02-14T15:30:00"
}
```

### GET `/api/search/{task_id}` - Get Task Status

**Response (completed):**
```json
{
  "task_id": "uuid",
  "status": "completed",
  "query": "What is the latest AI research?",
  "created_at": "2026-02-14T15:30:00",
  "completed_at": "2026-02-14T15:30:05",
  "result": {
    "query": "What is the latest AI research?",
    "search_depth": "basic",
    "topic": "general",
    "results": [...],
    "ai_answer": "Based on the search results...",
    "total_results": 10
  }
}
```

### POST `/api/search/sync` - Sync Search (Blocking)

Waits for search to complete before returning.

**Request:** Same as async

**Response:**
```json
{
  "success": true,
  "query": "What is the latest AI research?",
  "results": [...],
  "ai_answer": "Based on the search results...",
  "total_results": 10
}
```

### GET `/api/health` - Health Check

```json
{
  "status": "healthy",
  "tavily_configured": true,
  "siliconflow_configured": true,
  "active_tasks": 0
}
```

## Example Usage

### Using curl

```bash
# Async search
curl -X POST http://localhost:8080/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Latest breakthroughs in quantum computing",
    "search_depth": "advanced",
    "max_results": 5
  }'

# Sync search
curl -X POST http://localhost:8080/api/search/sync \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Latest breakthroughs in quantum computing",
    "search_depth": "advanced",
    "max_results": 5
  }'

# Check task status
curl http://localhost:8080/api/search/{task_id}
```

### Using Python

```python
import requests

# Sync search (simplest)
response = requests.post(
    "http://localhost:8080/api/search/sync",
    json={
        "query": "Latest breakthroughs in quantum computing",
        "search_depth": "advanced",
        "max_results": 5
    }
)
result = response.json()
print(result["ai_answer"])
```

### GET `/api/scrape` - Scrape URL

Scrape and extract content from a specific URL using Jina AI.

**Request:**
```bash
curl "http://localhost:8080/api/scrape?url=https://example.com/article"
```

**Response:**
```json
{
  "success": true,
  "url": "https://example.com/article",
  "content": "Extracted markdown content..."
}
```

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `TAVILY_API_KEY` | Tavily API key | Required |
| `TAVILY_BASE_URL` | Tavily API base URL | https://api.tavily.com |
| `JINA_API_KEY` | Jina AI API key | Optional |
| `JINA_BASE_URL` | Jina AI base URL | https://r.jina.ai |
| `SILICONFLOW_API_KEY` | SiliconFlow API key | Optional |
| `SILICONFLOW_BASE_URL` | SiliconFlow base URL | https://api.siliconflow.cn/v1 |
| `SILICONFLOW_MODEL` | Model name | Pro/zai-org/GLM-5 |
| `PORT` | Server port | 8080 |
| `HOST` | Server host | 0.0.0.0 |

## Search Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `query` | string | Search query (required) | - |
| `search_depth` | string | "basic" or "advanced" | "basic" |
| `max_results` | int | 1-100 | 10 |
| `include_answer` | bool | Include AI answer | true |
| `include_raw_content` | bool | Include raw HTML | false |
| `topic` | string | "general" or "news" | "general" |
| `days` | int | For news, days back (max 30) | null |

## Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│   Client    │────▶│  HTTP API       │────▶│   Tavily    │
│  (curl/py)  │◀────│  (FastAPI)      │◀────│   Search    │
└─────────────┘     └─────────────────┘     └─────────────┘
                            │
                            ▼
                    ┌─────────────────┐
                    │  SiliconFlow    │
                    │  GLM-5 (AI      │
                    │  answer gen)    │
                    └─────────────────┘
```

## Notes

- API keys are loaded from `.env` file (never commit real keys!)
- Task results are stored in memory (use Redis for production)
- Tavily is the primary search provider
- SiliconFlow GLM-5 is used for AI answer generation if Tavily doesn't provide one

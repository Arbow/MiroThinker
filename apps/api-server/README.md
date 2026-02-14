# HTTP API Server with Official MCP

Simple HTTP API for AI search using **official Tavily MCP** and SiliconFlow GLM-5.

## Features

- 🔍 **Official Tavily MCP**: Stable, maintained by Tavily team
- 🤖 **GLM-5 Integration**: AI answer generation using SiliconFlow
- ⚡ **Simple API**: RESTful endpoints with blocking and async modes
- 📊 **Health Monitoring**: Health check endpoint for monitoring

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) or conda
- **Node.js** (for official Tavily MCP)

### Install Node.js

```bash
# macOS
brew install node

# Ubuntu/Debian
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verify
node --version  # Should be v18+
npm --version
```

## Quick Start

### 1. Configure API Keys

```bash
cd apps/api-server
cp .env.example .env
# Edit .env with your actual API keys
```

### 2. Install Dependencies

**Using uv (recommended):**
```bash
uv sync
```

**Or using conda:**
```bash
conda create -n mirothinker-api python=3.10
conda activate mirothinker-api
pip install fastapi uvicorn httpx pydantic python-dotenv
```

### 3. Install Official Tavily MCP

```bash
# Install globally (recommended)
npm install -g tavily-mcp

# Or use npx directly (no install needed)
```

### 4. Start Server

```bash
# Using uv
./start.sh

# Or using conda
python main.py
```

Server will start at `http://localhost:8080`

## API Endpoints

### POST `/api/deep-research` - Deep Research (Multi-round)

**MiroThinker-style deep research** with iterative search and synthesis.

**Request:**
```json
{
  "query": "MiroThinker 在 AI 搜索上的亮点",
  "max_search_rounds": 3
}
```

**Response:**
```json
{
  "success": true,
  "query": "MiroThinker 在 AI 搜索上的亮点",
  "search_rounds": 3,
  "final_answer": "## 执行摘要...",
  "search_history": [
    {"round": 1, "query": "...", "result_count": 10},
    {"round": 2, "query": "...", "result_count": 10}
  ]
}
```

### POST `/api/search/sync` - Synchronous Search

**Request:**
```json
{
  "query": "What is the latest AI research?",
  "search_depth": "advanced",
  "max_results": 10
}
```

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
  "siliconflow_configured": true
}
```

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `TAVILY_API_KEY` | Tavily API key | Required |
| `TAVILY_BASE_URL` | Tavily API base URL | https://api.tavily.com |
| `SILICONFLOW_API_KEY` | SiliconFlow API key | Optional |
| `SILICONFLOW_BASE_URL` | SiliconFlow base URL | https://api.siliconflow.cn/v1 |
| `SILICONFLOW_MODEL` | Model name | Pro/zai-org/GLM-5 |
| `PORT` | Server port | 8080 |
| `HOST` | Server host | 0.0.0.0 |

## Using with Official MCP

For MiroThinker integration using official MCP servers:

```yaml
# conf/agent/tavily_official.yaml
defaults:
  - default
  - _self_

main_agent:
  tools:
    - tool-python
    - tavily-mcp  # Official Tavily MCP
  max_turns: 200

mcp_servers:
  tavily-mcp:
    command: npx
    args: ["-y", "tavily-mcp@latest"]
    env:
      TAVILY_API_KEY: ${TAVILY_API_KEY}
```

Run:
```bash
export TAVILY_API_KEY=your_key
uv run python main.py llm=qwen-3 agent=tavily_official llm.base_url=http://localhost:61002/v1
```

## Example Usage

### Using curl

```bash
# Sync search
curl -X POST http://localhost:8080/api/search/sync \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Latest breakthroughs in quantum computing",
    "search_depth": "advanced",
    "max_results": 5
  }'
```

### Using Python

```python
import requests

response = requests.post(
    "http://localhost:8080/api/search/sync",
    json={
        "query": "Latest AI research trends",
        "search_depth": "advanced",
        "max_results": 10
    }
)
result = response.json()
print(result["ai_answer"])
```

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

- Uses **official Tavily API** directly (HTTP API mode)
- For MiroThinker MCP integration, use `npx tavily-mcp`
- API keys loaded from `.env` (never commit!)

## References

- [Tavily Official MCP](https://github.com/tavily-ai/tavily-mcp)
- [Tavily API Docs](https://docs.tavily.com/)
- [SiliconFlow Docs](https://docs.siliconflow.cn/)

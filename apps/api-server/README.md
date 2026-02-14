# MiroThinker HTTP API Server

完整的 HTTP API 服务，支持：
1. **单次搜索** (Tavily)
2. **多轮深度研究** (简化版)
3. **真正的 MiroThinker Agent 调用** ⭐

## 快速开始

### 1. 配置环境变量

```bash
cd apps/api-server
cp .env.example .env
# 编辑 .env 填入你的 API Keys
```

### 2. 安装依赖

**基础模式**（单次搜索 + 多轮研究）：
```bash
uv sync
```

**完整模式**（包含 MiroThinker Agent）：
```bash
# Python 依赖
uv sync --extra mirothinker

# Node.js 依赖（Tavily MCP）
npm install -g tavily-mcp
```

### 3. 启动服务

```bash
./start.sh
# 或
uv run python main.py
```

服务启动在 `http://localhost:8080`

---

## API 端点

### 1. POST `/api/mirothinker/research` - 真正的 MiroThinker Agent ⭐

调用完整的 MiroThinker Agent 执行深度研究，支持多轮工具调用。

**请求：**
```json
{
  "query": "MiroThinker 在 AI 搜索上的亮点",
  "max_turns": 50
}
```

**响应：**
```json
{
  "success": true,
  "query": "MiroThinker 在 AI 搜索上的亮点",
  "task_id": "research_abc123",
  "final_answer": "## 执行摘要\n\nMiroThinker 是...",
  "thinking_process": "推理过程...",
  "tool_calls": ["tavily_search: {...}", ...],
  "log_file": "/tmp/mirothinker_logs/..."
}
```

**特点：**
- 真正的 MiroThinker Agent (Hydra 配置)
- 多轮工具调用（最多 50 轮）
- 完整的推理过程和工具调用日志

---

### 2. POST `/api/deep-research` - 多轮深度研究 ⭐

简化版多轮搜索，不需要 MiroThinker 依赖。

**请求参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| `query` | string | 研究主题（必填） |
| `max_search_rounds` | int | 搜索轮数（1-50，默认20） |
| `save_to_file` | bool | **直接保存报告到文件**（默认false） |
| `output_path` | string | 自定义输出路径（可选） |

**普通模式（返回完整内容）：**
```bash
curl -X POST http://localhost:8080/api/deep-research \
  -H "Content-Type: application/json" \
  -d '{"query": "量子计算最新进展", "max_search_rounds": 5}'
```

**文件保存模式（推荐用于博客发布）：**
```bash
curl -X POST http://localhost:8080/api/deep-research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "GLM 5.0 vs MiniMax M2.5 对比",
    "max_search_rounds": 20,
    "save_to_file": true
  }'
```

**文件保存模式响应：**
```json
{
  "success": true,
  "query": "GLM 5.0 vs MiniMax M2.5 对比",
  "search_rounds": 20,
  "file_saved": true,
  "file_path": "/Users/admin/.openclaw/workspace/20260214_164532_GLM_5_0_vs_MiniMax_M2_5_对比.md",
  "file_size": 15234,
  "note": "Full report saved to /Users/admin/.openclaw/workspace/... Use file content for publishing."
}
```

**优势：**
- ✅ 避免大量内容进入对话上下文
- ✅ 直接生成 Markdown 文件，方便发布博客
- ✅ 文件包含完整报告格式（标题、查询、搜索历史）

---

### 3. POST `/api/search/sync` - 单次搜索

快速单次搜索，立即返回结果。

**请求：**
```json
{
  "query": "搜索内容",
  "search_depth": "advanced",
  "max_results": 10
}
```

**响应：**
```json
{
  "success": true,
  "query": "搜索内容",
  "results": [...],
  "ai_answer": "AI 生成的综合分析...",
  "total_results": 10
}
```

---

### 4. GET `/api/health` - 健康检查

```bash
curl http://localhost:8080/api/health
```

**响应：**
```json
{
  "status": "healthy",
  "tavily_configured": true,
  "jina_configured": true,
  "siliconflow_configured": true,
  "mirothinker_available": true
}
```

---

## 调用示例

### 使用 curl

```bash
# 1. 真正的 MiroThinker Agent (推荐)
curl -X POST http://localhost:8080/api/mirothinker/research \
  -H "Content-Type: application/json" \
  -d '{"query": "最新 AI 技术趋势", "max_turns": 30}'

# 2. 多轮深度研究
curl -X POST http://localhost:8080/api/deep-research \
  -H "Content-Type: application/json" \
  -d '{"query": "量子计算进展", "max_search_rounds": 3}'

# 3. 单次快速搜索
curl -X POST http://localhost:8080/api/search/sync \
  -H "Content-Type: application/json" \
  -d '{"query": "OpenAI 新功能", "search_depth": "basic"}'
```

### 使用 Python

```python
import requests

# 真正的 MiroThinker Agent
response = requests.post(
    "http://localhost:8080/api/mirothinker/research",
    json={"query": "MiroThinker AI 搜索亮点", "max_turns": 50}
)
result = response.json()
print(result["final_answer"])
print(f"工具调用次数: {len(result['tool_calls'])}")
```

---

## 配置说明

### 环境变量

| 变量 | 说明 | 必需 |
|------|------|------|
| `TAVILY_API_KEY` | Tavily API Key | ✅ |
| `SILICONFLOW_API_KEY` | SiliconFlow API Key | ✅ (Agent 模式) |
| `SILICONFLOW_BASE_URL` | SiliconFlow Base URL | 可选 |
| `SILICONFLOW_MODEL` | 模型名称 | 默认: Pro/zai-org/GLM-5 |
| `JINA_API_KEY` | Jina API Key | 可选 |
| `PORT` | 服务端口 | 默认: 8080 |
| `HOST` | 服务地址 | 默认: 0.0.0.0 |

---

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                     HTTP API Server                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ /api/mirothinker │  │ /api/deep-       │  │ /api/search   │  │
│  │ /research        │  │ research         │  │ /sync         │  │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬───────┘  │
│           │                     │                    │          │
│           ▼                     ▼                    ▼          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ MiroThinkerAgent │  │ SimpleResearch   │  │ TavilySearch  │  │
│  │ (Hydra + MCP)    │  │ (Multi-round)    │  │ (Single)      │  │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬───────┘  │
│           │                     │                    │          │
│           ▼                     ▼                    ▼          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ Tavily MCP       │  │ Tavily API       │  │ Tavily API    │  │
│  │ SiliconFlow      │  │ SiliconFlow      │  │ SiliconFlow   │  │
│  │ GLM-5            │  │ GLM-5            │  │ GLM-5         │  │
│  └──────────────────┘  └──────────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三种模式的区别

| 特性 | MiroThinker Agent | 多轮深度研究 | 单次搜索 |
|------|-------------------|--------------|----------|
| **搜索次数** | 多轮 (可达 50+) | 2-10 轮 | 1 轮 |
| **推理深度** | ⭐⭐⭐ 深度 | ⭐⭐ 中等 | ⭐ 浅层 |
| **工具调用** | ✅ 完整 | ⚠️ 简化 | ❌ 无 |
| **依赖** | Hydra + MCP | 仅 API | 仅 API |
| **启动速度** | 较慢 | 快 | 最快 |
| **适用场景** | 复杂研究 | 一般研究 | 快速查询 |

---

## 故障排除

### "MiroThinker agent not available"

```bash
# 安装缺少的依赖
uv sync --extra mirothinker
npm install -g tavily-mcp
```

### "TAVILY_API_KEY not configured"

```bash
# 检查 .env 文件
cat .env | grep TAVILY

# 或手动导出
export TAVILY_API_KEY=your_key_here
```

### 导入错误

确保从 `apps/api-server` 目录运行：
```bash
cd apps/api-server
uv run python main.py
```

---

## 参考

- [MiroThinker GitHub](https://github.com/MiroMindAI/MiroFlow)
- [Tavily API Docs](https://docs.tavily.com/)
- [SiliconFlow Docs](https://docs.siliconflow.cn/)

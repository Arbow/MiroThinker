# Firecrawl & Tavily MCP Servers for MiroThinker

This document describes how to use Firecrawl and Tavily as alternative search providers in MiroThinker.

## Overview

MiroThinker now supports multiple search providers through MCP (Model Context Protocol):

| Provider | Strengths | Best For |
|----------|-----------|----------|
| **Serper** (default) | Google search, fast, cost-effective | General web search |
| **Firecrawl** | Search + scrape in one, clean markdown | Deep research, content extraction |
| **Tavily** | AI-optimized, relevance scoring, AI answers | AI agent workflows, news search |

## Firecrawl MCP Server

### Features
- **Unified search + scrape**: Get search results with full markdown content
- **Clean extraction**: Automatically converts web pages to clean markdown
- **Flexible scraping**: Scrape specific URLs with format options

### Configuration

1. Get API key from [firecrawl.dev](https://firecrawl.dev)

2. Add to `.env`:
```bash
FIRECRAWL_API_KEY=your_firecrawl_key
# Optional: custom endpoint
# FIRECRAWL_BASE_URL=https://your-firecrawl-instance.com/v1
```

3. Use Firecrawl configuration:
```bash
uv run python main.py \
    llm=qwen-3 \
    agent=firecrawl_demo \
    llm.base_url=http://localhost:61002/v1
```

### Available Tools

#### `firecrawl_search`
Search the web with optional content scraping.

Parameters:
- `q`: Search query (required)
- `limit`: Number of results (default: 10, max: 100)
- `lang`: Language code (e.g., 'en', 'zh')
- `country`: Country code (e.g., 'us', 'cn')
- `scrape_options`: Dict with scraping options
  - `formats`: ['markdown', 'html', 'screenshot']
  - `only_main_content`: boolean

Example result:
```json
{
  "success": true,
  "organic": [
    {
      "title": "Page Title",
      "link": "https://example.com",
      "snippet": "Description...",
      "markdown": "# Full content in markdown..."
    }
  ],
  "totalResults": 10
}
```

#### `firecrawl_scrape`
Scrape content from a specific URL.

Parameters:
- `url`: URL to scrape (required)
- `formats`: List of formats ['markdown', 'html', 'screenshot']
- `only_main_content`: Extract main content only (default: true)
- `wait_for`: Time to wait for page load (ms)

## Tavily MCP Server

### Features
- **AI-optimized search**: Specifically designed for AI agents
- **AI-generated answers**: Get synthesized answers to queries
- **Relevance scoring**: Each result has a relevance score
- **News search**: Time-based filtering for news topics
- **Domain filtering**: Include/exclude specific domains

### Configuration

1. Get API key from [tavily.com](https://tavily.com)

2. Add to `.env`:
```bash
TAVILY_API_KEY=your_tavily_key
# Optional: custom endpoint
# TAVILY_BASE_URL=https://your-tavily-instance.com
```

3. Use Tavily configuration:
```bash
uv run python main.py \
    llm=qwen-3 \
    agent=tavily_demo \
    llm.base_url=http://localhost:61002/v1
```

### Available Tools

#### `tavily_search`
AI-optimized web search.

Parameters:
- `q`: Search query (required)
- `search_depth`: 'basic' (fast) or 'advanced' (comprehensive)
- `include_answer`: Include AI-generated answer (default: true)
- `include_raw_content`: Include full page content (default: false)
- `max_results`: Number of results (default: 10, max: 100)
- `include_domains`: List of domains to include (e.g., ['arxiv.org'])
- `exclude_domains`: List of domains to exclude
- `topic`: 'general' or 'news'
- `days`: For news, days back to search (max: 30)

Example result:
```json
{
  "success": true,
  "organic": [
    {
      "title": "Page Title",
      "link": "https://example.com",
      "snippet": "Content snippet...",
      "score": 0.95
    }
  ],
  "answer": "AI-generated answer to the query...",
  "query": "original query"
}
```

#### `tavily_extract`
Extract content from specific URLs.

Parameters:
- `urls`: List of URLs to extract (max: 20)
- `extract_depth`: 'basic' or 'advanced'
- `include_images`: Include images (default: false)

## Comparison: Serper vs Firecrawl vs Tavily

| Feature | Serper | Firecrawl | Tavily |
|---------|--------|-----------|--------|
| **Search Engine** | Google | Aggregated | Aggregated |
| **Response Speed** | ⚡ Fast | 🚀 Medium | 🚀 Medium |
| **Content Scraping** | ❌ No | ✅ Yes (built-in) | ✅ Yes (optional) |
| **AI Answer** | ❌ No | ❌ No | ✅ Yes |
| **Relevance Score** | ❌ No | ❌ No | ✅ Yes |
| **News Filtering** | ⚠️ Limited | ❌ No | ✅ Yes |
| **Domain Filter** | ⚠️ Limited | ❌ No | ✅ Yes |
| **Pricing** | $ | $$ | $$ |

## Custom Configuration

You can create custom configurations combining multiple search providers:

```yaml
# conf/agent/hybrid_search.yaml
defaults:
  - default
  - _self_

main_agent:
  tools:
    - tool-python
    - google_search           # Serper for general search
    - firecrawl-search        # Firecrawl for deep content
    - tavily-search          # Tavily for AI answers
    - jina_scrape_llm_summary
  max_turns: 200
```

The agent will intelligently select the appropriate tool based on the task.

## Migration from Serper

To switch from Serper to Firecrawl or Tavily:

1. Update your `.env` file with the new API key
2. Change the agent configuration:
   - From: `agent=mirothinker_v1.5_keep5_max200`
   - To: `agent=firecrawl_demo` or `agent=tavily_demo`
3. No code changes needed - the agent interface is compatible

## Troubleshooting

### "API key not set" error
Make sure the environment variable is set in `.env` and the file is loaded.

### Empty results
- Check your API key is valid
- Verify you have API credits
- Check API rate limits

### Timeout errors
- Firecrawl scraping can take longer (increase timeout in config)
- Tavily advanced search is slower than basic

## License

These MCP servers follow the same MIT license as MiroThinker.

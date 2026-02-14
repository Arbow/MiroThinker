# Official MCP Servers Configuration

MiroThinker supports using official MCP (Model Context Protocol) servers from Tavily and Firecrawl.

## Why Official MCP?

- ✅ **Stability** - Maintained by the official teams
- ✅ **Updates** - Automatic feature updates
- ✅ **Community** - Active support and bug fixes
- ⚠️ **Requirement** - Node.js runtime needed

## Prerequisites

```bash
# Install Node.js (if not already installed)
# macOS
brew install node

# Ubuntu/Debian
sudo apt-get install nodejs npm

# Or download from https://nodejs.org/
```

## Tavily Official MCP

### Installation

```bash
# Install globally
npm install -g tavily-mcp

# Or use with npx (no installation needed)
npx -y tavily-mcp@latest
```

### Configuration

Create `conf/agent/tavily_official.yaml`:

```yaml
defaults:
  - default
  - _self_

main_agent:
  tools:
    - tool-python
    - tavily-mcp  # Official Tavily MCP
  max_turns: 200

# MCP server configuration
mcp_servers:
  tavily-mcp:
    command: npx
    args: ["-y", "tavily-mcp@latest"]
    env:
      TAVILY_API_KEY: ${TAVILY_API_KEY}
```

### Environment Variables

```bash
# .env
TAVILY_API_KEY=your_tavily_api_key
```

### Available Tools

- `tavily_search` - Search the web with AI-optimized results
- `tavily_extract` - Extract content from URLs

## Firecrawl Official MCP

### Installation

```bash
# Install globally
npm install -g @mendable/firecrawl-mcp

# Or use with npx
npx -y @mendable/firecrawl-mcp
```

### Configuration

Create `conf/agent/firecrawl_official.yaml`:

```yaml
defaults:
  - default
  - _self_

main_agent:
  tools:
    - tool-python
    - firecrawl-mcp  # Official Firecrawl MCP
  max_turns: 200

# MCP server configuration
mcp_servers:
  firecrawl-mcp:
    command: npx
    args: ["-y", "@mendable/firecrawl-mcp"]
    env:
      FIRECRAWL_API_KEY: ${FIRECRAWL_API_KEY}
```

### Environment Variables

```bash
# .env
FIRECRAWL_API_KEY=your_firecrawl_api_key
```

### Available Tools

- `firecrawl_scrape` - Scrape web pages to markdown
- `firecrawl_search` - Search and scrape in one call
- `firecrawl_crawl` - Crawl multiple pages
- `firecrawl_map` - Generate site maps

## Combined Configuration

Use multiple search providers together:

```yaml
# conf/agent/multi_search.yaml
defaults:
  - default
  - _self_

main_agent:
  tools:
    - tool-python
    - serper-mcp        # Default Google search
    - tavily-mcp        # AI-optimized search
    - firecrawl-mcp     # Search + scrape
  max_turns: 200

mcp_servers:
  serper-mcp:
    command: python
    args: ["-m", "miroflow_tools.mcp_servers.serper_mcp_server"]
    
  tavily-mcp:
    command: npx
    args: ["-y", "tavily-mcp@latest"]
    env:
      TAVILY_API_KEY: ${TAVILY_API_KEY}
      
  firecrawl-mcp:
    command: npx
    args: ["-y", "@mendable/firecrawl-mcp"]
    env:
      FIRECRAWL_API_KEY: ${FIRECRAWL_API_KEY}
```

## Usage

### Run with Tavily

```bash
cd apps/miroflow-agent

# Set environment variables
export TAVILY_API_KEY=your_key

# Run with Tavily configuration
uv run python main.py \
    llm=qwen-3 \
    agent=tavily_official \
    llm.base_url=http://localhost:61002/v1
```

### Run with Firecrawl

```bash
# Set environment variables
export FIRECRAWL_API_KEY=your_key

# Run with Firecrawl configuration
uv run python main.py \
    llm=qwen-3 \
    agent=firecrawl_official \
    llm.base_url=http://localhost:61002/v1
```

## Troubleshooting

### "npx command not found"

```bash
# Install Node.js
brew install node  # macOS
# or
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs  # Ubuntu
```

### MCP server timeout

Add timeout configuration:

```yaml
mcp_servers:
  tavily-mcp:
    command: npx
    args: ["-y", "tavily-mcp@latest"]
    env:
      TAVILY_API_KEY: ${TAVILY_API_KEY}
    timeout: 120  # seconds
```

### API key not recognized

Ensure environment variables are exported:

```bash
# Check if set
echo $TAVILY_API_KEY

# Export explicitly
export TAVILY_API_KEY=your_actual_key
```

## References

- [Tavily MCP Repository](https://github.com/tavily-ai/tavily-mcp)
- [Firecrawl MCP Repository](https://github.com/mendableai/firecrawl-mcp-server)
- [MCP Specification](https://modelcontextprotocol.io/)

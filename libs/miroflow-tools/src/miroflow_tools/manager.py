# Copyright (c) 2025 MiroMind
# This source code is licensed under the Apache 2.0 License.

import asyncio
import functools
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol, TypeVar
from urllib.parse import urlsplit, urlunsplit

from fastmcp import Client as FastMCPClient
from fastmcp.client.transports import (
    SSETransport,
    StdioTransport,
    StreamableHttpTransport,
)
from mcp import StdioServerParameters  # (already imported in config.py)

from .mcp_servers.browser_session import PlaywrightSession

# logger = logging.getLogger("miroflow_agent")

R = TypeVar("R")


def with_timeout(timeout_s: float = 300.0):
    """
    Decorator: wraps any *async* function in asyncio.wait_for().
    Usage:
        @with_timeout(20)
        async def create_message_foo(...): ...
    """

    def decorator(
        func: Callable[..., Awaitable[R]],
    ) -> Callable[..., Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> R:
            return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_s)

        return wrapper

    return decorator


class ToolManagerProtocol(Protocol):
    """this enables other kinds of tool manager."""

    def get_all_tool_definitions(self) -> Awaitable[Any]: ...

    def execute_tool_call(
        self, *, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> Awaitable[Any]: ...


class ToolManager(ToolManagerProtocol):
    def __init__(self, server_configs, tool_blacklist=None):
        """
        Initialize ToolManager.
        :param server_configs: List returned by create_server_parameters()
        """
        self.server_configs = server_configs
        self.server_dict = {
            config["name"]: config["params"] for config in server_configs
        }
        self.browser_session = None
        self.tool_blacklist = tool_blacklist if tool_blacklist else set()
        self.task_log = None
        self._remote_clients: dict[str, FastMCPClient] = {}
        self._remote_clients_lock = asyncio.Lock()

    async def aclose(self) -> None:
        """Close any persistent remote clients / sessions."""
        async with self._remote_clients_lock:
            clients = list(self._remote_clients.items())
            self._remote_clients = {}

        for server_name, client in clients:
            try:
                await client.__aexit__(None, None, None)
            except Exception as e:
                self._log(
                    "warning",
                    "ToolManager | Close Remote Client Failed",
                    f"Failed to close remote client for '{server_name}': {e}",
                )

        # Close browser session if present
        if self.browser_session is not None:
            try:
                await self.browser_session.close()
            except Exception:
                pass
            finally:
                self.browser_session = None

    async def _get_or_create_remote_client(
        self, server_name: str, server_params: dict[str, Any]
    ) -> FastMCPClient:
        existing = self._remote_clients.get(server_name)
        if existing is not None:
            return existing

        async with self._remote_clients_lock:
            existing = self._remote_clients.get(server_name)
            if existing is not None:
                return existing

            url = server_params["url"]
            headers = server_params.get("headers")
            transport_type = (server_params.get("type") or "sse").lower()
            timeout = server_params.get("timeout", 120)
            init_timeout = server_params.get("init_timeout", 30)
            sse_read_timeout = server_params.get("sse_read_timeout", 300)

            if transport_type in {"streamablehttp", "streamable_http", "http"}:
                transport = StreamableHttpTransport(
                    url=url, headers=headers, sse_read_timeout=sse_read_timeout
                )
            else:
                transport = SSETransport(
                    url=url, headers=headers, sse_read_timeout=sse_read_timeout
                )

            client = FastMCPClient(
                transport, timeout=timeout, init_timeout=init_timeout
            )
            await client.__aenter__()
            self._remote_clients[server_name] = client
            return client

    async def _get_or_create_stdio_client(
        self, server_name: str, server_params: StdioServerParameters
    ) -> FastMCPClient:
        existing = self._remote_clients.get(server_name)
        if existing is not None:
            return existing

        async with self._remote_clients_lock:
            existing = self._remote_clients.get(server_name)
            if existing is not None:
                return existing

            cwd = server_params.cwd
            cwd_str = str(cwd) if isinstance(cwd, (str, Path)) and cwd else None
            transport = StdioTransport(
                command=server_params.command,
                args=server_params.args,
                env=server_params.env,
                cwd=cwd_str,
                keep_alive=True,
            )
            client = FastMCPClient(transport, timeout=120, init_timeout=30)
            await client.__aenter__()
            self._remote_clients[server_name] = client
            return client

    async def _get_or_create_sse_url_client(
        self, server_name: str, url: str
    ) -> FastMCPClient:
        existing = self._remote_clients.get(server_name)
        if existing is not None:
            return existing

        async with self._remote_clients_lock:
            existing = self._remote_clients.get(server_name)
            if existing is not None:
                return existing

            transport = SSETransport(url=url, headers=None, sse_read_timeout=300)
            client = FastMCPClient(transport, timeout=120, init_timeout=30)
            await client.__aenter__()
            self._remote_clients[server_name] = client
            return client

    def set_task_log(self, task_log):
        """Set the task logger for structured logging."""
        self.task_log = task_log

        self._log(
            "info",
            "ToolManager | Initialization",
            f"ToolManager initialized, loaded servers: {list(self.server_dict.keys())}",
        )

    def _log(self, level, step_name, message, metadata=None):
        """Helper method to log using task_log if available, otherwise skip logging."""
        if self.task_log:
            self.task_log.log_step(level, step_name, message, metadata)

    def _summarize_arguments(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Return a compact, safe argument summary for logs."""
        if not isinstance(arguments, dict):
            return ""

        def _sanitize_url(raw: str) -> str:
            value = (raw or "").strip()
            if not value:
                return ""
            try:
                parts = urlsplit(value)
                # Drop query/fragment to reduce chance of leaking tokens.
                return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
            except Exception:
                return value.split("?", 1)[0].split("#", 1)[0]

        if "url" in arguments and isinstance(arguments.get("url"), str):
            sanitized = _sanitize_url(arguments.get("url", ""))
            return f"url={sanitized}" if sanitized else ""

        # Common search argument keys
        for key in ("q", "query", "Query"):
            if key in arguments and isinstance(arguments.get(key), str):
                text = (arguments.get(key) or "").strip()
                if text:
                    text = text.replace("\n", " ")
                    if len(text) > 120:
                        text = text[:120] + "..."
                    return f"{key}={text}"

        return ""

    def _is_huggingface_dataset_or_space_url(self, url):
        """
        Check if the URL is a Hugging Face dataset or space URL.
        :param url: The URL to check
        :return: True if it's a HuggingFace dataset or space URL, False otherwise
        """
        if not url:
            return False
        return "huggingface.co/datasets" in url or "huggingface.co/spaces" in url

    def _should_block_hf_scraping(self, tool_name, arguments):
        """
        Check if we should block scraping of Hugging Face datasets/spaces.
        :param tool_name: The name of the tool being called
        :param arguments: The arguments passed to the tool
        :return: True if scraping should be blocked, False otherwise
        """
        return (
            tool_name in ["scrape", "scrape_website", "webReader"]
            and arguments.get("url")
            and self._is_huggingface_dataset_or_space_url(arguments["url"])
        )

    def get_server_params(self, server_name):
        """Get parameters for the specified server"""
        return self.server_dict.get(server_name)

    async def get_all_tool_definitions(self):
        """
        Connect to all configured servers and get their tool definitions.
        Returns a list suitable for passing to the Prompt generator.
        """
        all_servers_for_prompt = []
        # Process remote server tools
        for config in self.server_configs:
            server_name = config["name"]
            server_params = config["params"]
            one_server_for_prompt = {"name": server_name, "tools": []}
            self._log(
                "info",
                "ToolManager | Get Tool Definitions",
                f"Getting tool definitions for server '{server_name}'...",
            )

            try:
                if isinstance(server_params, StdioServerParameters):
                    client = await self._get_or_create_stdio_client(
                        server_name, server_params
                    )
                    tools_response = await client.list_tools()
                    for tool in tools_response:
                        if (server_name, tool.name) in self.tool_blacklist:
                            self._log(
                                "info",
                                "ToolManager | Tool Blacklisted",
                                f"Tool '{tool.name}' in server '{server_name}' is blacklisted, skipping.",
                            )
                            continue
                        one_server_for_prompt["tools"].append(
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "schema": tool.inputSchema,
                            }
                        )
                elif isinstance(server_params, str) and server_params.startswith(
                    ("http://", "https://")
                ):
                    client = await self._get_or_create_sse_url_client(
                        server_name, server_params
                    )
                    tools_response = await client.list_tools()
                    for tool in tools_response:
                        if (server_name, tool.name) in self.tool_blacklist:
                            self._log(
                                "info",
                                "ToolManager | Tool Blacklisted",
                                f"Tool '{tool.name}' in server '{server_name}' is blacklisted, skipping.",
                            )
                            continue
                        one_server_for_prompt["tools"].append(
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "schema": tool.inputSchema,
                            }
                        )
                elif isinstance(server_params, dict) and "url" in server_params:
                    client = await self._get_or_create_remote_client(
                        server_name, server_params
                    )
                    tools_response = await client.list_tools()
                    for tool in tools_response:
                        if (server_name, tool.name) in self.tool_blacklist:
                            self._log(
                                "info",
                                "ToolManager | Tool Blacklisted",
                                f"Tool '{tool.name}' in server '{server_name}' is blacklisted, skipping.",
                            )
                            continue
                        one_server_for_prompt["tools"].append(
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "schema": tool.inputSchema,
                            }
                        )
                else:
                    self._log(
                        "error",
                        "ToolManager | Unknown Parameter Type",
                        f"Error: Unknown parameter type for server '{server_name}': {type(server_params)}",
                    )
                    raise TypeError(
                        f"Unknown server params type for {server_name}: {type(server_params)}"
                    )

                self._log(
                    "info",
                    "ToolManager | Tool Definitions Success",
                    f"Successfully obtained {len(one_server_for_prompt['tools'])} tool definitions from server '{server_name}'.",
                )
                all_servers_for_prompt.append(one_server_for_prompt)

            except Exception as e:
                self._log(
                    "error",
                    "ToolManager | Connection Error",
                    f"Error: Unable to connect or get tools from server '{server_name}': {e}",
                )
                # Still add server entry, but mark tool list as empty or include error information
                one_server_for_prompt["tools"] = [
                    {"error": f"Unable to fetch tools: {e}"}
                ]
                all_servers_for_prompt.append(one_server_for_prompt)

        return all_servers_for_prompt

    @with_timeout(1200)
    async def execute_tool_call(self, server_name, tool_name, arguments) -> Any:
        """
        Execute a single tool call.
        :param server_name: Server name
        :param tool_name: Tool name
        :param arguments: Tool arguments dictionary
        :return: Dictionary containing result or error
        """

        # Original remote server call logic
        server_params = self.get_server_params(server_name)
        if not server_params:
            self._log(
                "error",
                "ToolManager | Server Not Found",
                f"Error: Attempting to call server '{server_name}' not found",
            )
            return {
                "server_name": server_name,
                "tool_name": tool_name,
                "error": f"Server '{server_name}' not found.",
            }

        self._log(
            "info",
            "ToolManager | Tool Call Start",
            f"Connecting to server '{server_name}' to call tool '{tool_name}'",
            metadata={"arguments": arguments},
        )

        if server_name == "playwright":
            try:
                if self.browser_session is None:
                    self.browser_session = PlaywrightSession(server_params)
                    await self.browser_session.connect()
                tool_result = await self.browser_session.call_tool(
                    tool_name, arguments=arguments
                )
                return {
                    "server_name": server_name,
                    "tool_name": tool_name,
                    "result": tool_result,
                }
            except Exception as e:
                return {
                    "server_name": server_name,
                    "tool_name": tool_name,
                    "error": f"Tool call failed: {str(e)}",
                }
        else:
            try:
                result_content = None
                if isinstance(server_params, StdioServerParameters):
                    client = await self._get_or_create_stdio_client(
                        server_name, server_params
                    )
                    try:
                        tool_result = await client.call_tool(tool_name, arguments)
                        result_content = (
                            tool_result.content[-1].text if tool_result.content else ""
                        )
                        if self._should_block_hf_scraping(tool_name, arguments):
                            result_content = "You are trying to scrape a Hugging Face dataset for answers, please do not use the scrape tool for this purpose."
                    except Exception as tool_error:
                        self._log(
                            "error",
                            "ToolManager | Tool Execution Error",
                            f"Tool execution error: tool={tool_name} server={server_name} {self._summarize_arguments(tool_name, arguments)} err={tool_error}",
                        )
                        return {
                            "server_name": server_name,
                            "tool_name": tool_name,
                            "error": f"Tool execution failed: {str(tool_error)}",
                        }
                elif isinstance(server_params, str) and server_params.startswith(
                    ("http://", "https://")
                ):
                    client = await self._get_or_create_sse_url_client(
                        server_name, server_params
                    )
                    try:
                        tool_result = await client.call_tool(tool_name, arguments)
                        result_content = (
                            tool_result.content[-1].text if tool_result.content else ""
                        )
                        if self._should_block_hf_scraping(tool_name, arguments):
                            result_content = "You are trying to scrape a Hugging Face dataset for answers, please do not use the scrape tool for this purpose."
                    except Exception as tool_error:
                        self._log(
                            "error",
                            "ToolManager | Tool Execution Error",
                            f"Tool execution error: tool={tool_name} server={server_name} {self._summarize_arguments(tool_name, arguments)} err={tool_error}",
                        )
                        return {
                            "server_name": server_name,
                            "tool_name": tool_name,
                            "error": f"Tool execution failed: {str(tool_error)}",
                        }
                elif isinstance(server_params, dict) and "url" in server_params:
                    client = await self._get_or_create_remote_client(
                        server_name, server_params
                    )
                    try:
                        tool_result = await client.call_tool(tool_name, arguments)
                        if tool_result.content:
                            result_content = tool_result.content[-1].text
                        else:
                            result_content = ""

                        if self._should_block_hf_scraping(tool_name, arguments):
                            result_content = "You are trying to scrape a Hugging Face dataset for answers, please do not use the scrape tool for this purpose."
                    except Exception as tool_error:
                        self._log(
                            "error",
                            "ToolManager | Tool Execution Error",
                            f"Tool execution error: tool={tool_name} server={server_name} {self._summarize_arguments(tool_name, arguments)} err={tool_error}",
                        )
                        return {
                            "server_name": server_name,
                            "tool_name": tool_name,
                            "error": f"Tool execution failed: {str(tool_error)}",
                        }
                else:
                    raise TypeError(
                        f"Unknown server params type for {server_name}: {type(server_params)}"
                    )

                self._log(
                    "info",
                    "ToolManager | Tool Call Success",
                    f"Tool '{tool_name}' (server: '{server_name}') called successfully.",
                )

                return {
                    "server_name": server_name,
                    "tool_name": tool_name,
                    "result": result_content,  # Return extracted text content
                }

            except Exception as outer_e:  # Rename this to outer_e to avoid shadowing
                self._log(
                    "error",
                    "ToolManager | Tool Call Failed",
                    f"Error: Failed to call tool '{tool_name}' (server: '{server_name}'): {outer_e}",
                )

                # Store the original error message for later use
                error_message = str(outer_e)

                if (
                    tool_name in ["scrape", "scrape_website"]
                    and "unhandled errors" in error_message
                    and "url" in arguments
                    and arguments["url"] is not None
                ):
                    try:
                        self._log(
                            "info",
                            "ToolManager | Fallback Attempt",
                            "Attempting fallback using MarkItDown...",
                        )
                        from markitdown import MarkItDown

                        md = MarkItDown(
                            docintel_endpoint="<document_intelligence_endpoint>"
                        )
                        result = md.convert(arguments["url"])
                        self._log(
                            "info",
                            "ToolManager | Fallback Success",
                            "MarkItDown fallback successful",
                        )
                        return {
                            "server_name": server_name,
                            "tool_name": tool_name,
                            "result": result.text_content,  # Return extracted text content
                        }
                    except (
                        Exception
                    ) as inner_e:  # Use a different name to avoid shadowing
                        # Log the inner exception if needed
                        self._log(
                            "error",
                            "ToolManager | Fallback Failed",
                            f"Fallback also failed: {inner_e}",
                        )
                        # No need for pass here as we'll continue to the return statement

                # Always use the outer exception for the final error response
                return {
                    "server_name": server_name,
                    "tool_name": tool_name,
                    "error": f"Tool call failed: {error_message}",
                }

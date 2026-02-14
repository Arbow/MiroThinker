# Copyright (c) 2025 MiroMind
# This source code is licensed under the MIT License.

"""
MiroThinker Agent Integration for HTTP API

This module provides programmatic access to MiroThinker's deep research capabilities
via HTTP API, without using subprocess.
"""

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from omegaconf import DictConfig, OmegaConf

# Import MiroFlow components from miroflow-agent package
from src.core.pipeline import (
    create_pipeline_components,
    execute_task_pipeline,
)
from src.logging.task_logger import bootstrap_logger
from src.logging.task_logger import bootstrap_logger


class MiroThinkerAgent:
    """
    Wrapper class to run MiroThinker agent programmatically
    """
    
    def __init__(
        self,
        tavily_api_key: Optional[str] = None,
        siliconflow_api_key: Optional[str] = None,
        siliconflow_base_url: str = "https://api.siliconflow.cn/v1",
        siliconflow_model: str = "Pro/zai-org/GLM-5",
        jina_api_key: Optional[str] = None,
        jina_base_url: str = "https://r.jina.ai",
        max_turns: int = 50,
        agent_config: str = "tavily_official",
    ):
        """
        Initialize MiroThinker Agent
        
        Args:
            tavily_api_key: Tavily API key
            siliconflow_api_key: SiliconFlow API key
            siliconflow_base_url: SiliconFlow base URL
            siliconflow_model: Model name (default: Pro/zai-org/GLM-5)
            jina_api_key: Jina API key for web scraping
            jina_base_url: Jina base URL (default: https://r.jina.ai)
            max_turns: Maximum agent turns (default: 50)
            agent_config: Agent configuration name (default: tavily_official)
        """
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY", "")
        self.siliconflow_api_key = siliconflow_api_key or os.getenv("SILICONFLOW_API_KEY", "")
        self.siliconflow_base_url = siliconflow_base_url
        self.siliconflow_model = siliconflow_model
        self.jina_api_key = jina_api_key or os.getenv("JINA_API_KEY", "")
        self.jina_base_url = jina_base_url
        self.max_turns = max_turns
        self.agent_config = agent_config
        
        # Setup logger
        self.logger = bootstrap_logger()
        
    def _create_config(self) -> DictConfig:
        """Create Hydra configuration for the agent"""
        
        # Get the path to jina_scrape_llm_summary.py
        jina_mcp_path = Path(__file__).parent.parent / "libs" / "miroflow-tools" / "src" / "miroflow_tools" / "dev_mcp_servers" / "jina_scrape_llm_summary.py"
        
        # Base configuration
        config_dict = {
            "defaults": [
                "_self_",
                {"agent": self.agent_config},
                {"llm": "default"},
            ],
            "main_agent": {
                "max_turns": self.max_turns,
            },
            "llm": {
                "base_url": self.siliconflow_base_url,
                "api_key": self.siliconflow_api_key,
                "model": self.siliconflow_model,
            },
            "mcp_servers": {
                "tavily-mcp": {
                    "command": "npx",
                    "args": ["-y", "tavily-mcp@latest"],
                    "env": {
                        "TAVILY_API_KEY": self.tavily_api_key,
                    },
                },
                "jina-scrape-llm-summary": {
                    "command": "python",
                    "args": [str(jina_mcp_path)],
                    "env": {
                        "JINA_API_KEY": self.jina_api_key,
                        "JINA_BASE_URL": self.jina_base_url,
                        "SUMMARY_LLM_BASE_URL": self.siliconflow_base_url,
                        "SUMMARY_LLM_MODEL_NAME": self.siliconflow_model,
                        "SUMMARY_LLM_API_KEY": self.siliconflow_api_key,
                    },
                },
            },
            "debug_dir": "/tmp/mirothinker_logs",
        }
        
        return OmegaConf.create(config_dict)
    
    async def research(self, query: str) -> Dict[str, Any]:
        """
        Execute deep research on a query
        
        Args:
            query: The research query
            
        Returns:
            Dict containing:
            - success: bool
            - query: str
            - final_answer: str
            - thinking_process: str
            - tool_calls: list
            - error: str (if failed)
        """
        
        if not self.tavily_api_key:
            raise ValueError("TAVILY_API_KEY not configured")
        
        if not self.siliconflow_api_key:
            raise ValueError("SILICONFLOW_API_KEY not configured")
        
        # Create configuration
        cfg = self._create_config()
        
        # Create pipeline components
        self.logger.info("Initializing MiroThinker pipeline components...")
        
        try:
            main_agent_tool_manager, sub_agent_tool_managers, output_formatter = (
                create_pipeline_components(cfg)
            )
        except Exception as e:
            return {
                "success": False,
                "query": query,
                "error": f"Failed to initialize pipeline: {str(e)}",
            }
        
        # Generate unique task ID
        task_id = f"research_{uuid.uuid4().hex[:8]}"
        
        self.logger.info(f"Starting research task: {task_id}")
        self.logger.info(f"Query: {query}")
        
        try:
            # Execute the research pipeline
            final_summary, final_boxed_answer, log_file_path, failure_experience = (
                await execute_task_pipeline(
                    cfg=cfg,
                    task_id=task_id,
                    task_description=query,
                    task_file_name="",
                    main_agent_tool_manager=main_agent_tool_manager,
                    sub_agent_tool_managers=sub_agent_tool_managers,
                    output_formatter=output_formatter,
                    log_dir=cfg.debug_dir,
                )
            )
            
            self.logger.info(f"Research completed: {task_id}")
            
            # Extract thinking process and tool calls from log if available
            thinking_process = ""
            tool_calls = []
            
            if log_file_path and os.path.exists(log_file_path):
                try:
                    with open(log_file_path, 'r', encoding='utf-8') as f:
                        log_content = f.read()
                        # Extract tool calls and reasoning from log
                        thinking_process = self._extract_thinking(log_content)
                        tool_calls = self._extract_tool_calls(log_content)
                except Exception as e:
                    self.logger.warning(f"Failed to parse log file: {e}")
            
            return {
                "success": True,
                "query": query,
                "task_id": task_id,
                "final_answer": final_boxed_answer or final_summary,
                "thinking_process": thinking_process,
                "tool_calls": tool_calls,
                "log_file": log_file_path,
            }
            
        except Exception as e:
            self.logger.error(f"Research failed: {e}")
            return {
                "success": False,
                "query": query,
                "task_id": task_id,
                "error": str(e),
            }
    
    def _extract_thinking(self, log_content: str) -> str:
        """Extract thinking/reasoning process from log"""
        lines = []
        for line in log_content.split('\n'):
            if 'reasoning' in line.lower() or 'thinking' in line.lower() or 'step' in line.lower():
                lines.append(line)
        return '\n'.join(lines[-50:])  # Last 50 thinking lines
    
    def _extract_tool_calls(self, log_content: str) -> list:
        """Extract tool calls from log"""
        tool_calls = []
        for line in log_content.split('\n'):
            if 'tool' in line.lower() and ('call' in line.lower() or 'invoke' in line.lower()):
                tool_calls.append(line.strip())
        return tool_calls[-20:]  # Last 20 tool calls


# Singleton instance for reuse
_agent_instance: Optional[MiroThinkerAgent] = None


def get_agent() -> MiroThinkerAgent:
    """Get or create singleton agent instance"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = MiroThinkerAgent()
    return _agent_instance


async def run_mirothinker_research(query: str) -> Dict[str, Any]:
    """
    Convenience function to run MiroThinker research
    
    Args:
        query: Research query
        
    Returns:
        Research results dict
    """
    agent = get_agent()
    return await agent.research(query)

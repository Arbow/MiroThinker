# Copyright (c) 2025 MiroMind
# This source code is licensed under the Apache 2.0 License.

import asyncio

import hydra
from omegaconf import DictConfig, OmegaConf

# Import from the new modular structure
from src.core.pipeline import (
    create_pipeline_components,
    execute_task_pipeline,
)
from src.logging.task_logger import bootstrap_logger

# Configure logger and get the configured instance
logger = bootstrap_logger()


async def amain(cfg: DictConfig) -> None:
    """Asynchronous main function."""

    # Avoid logging secrets (e.g., llm.api_key from env interpolation)
    safe_cfg = {
        "llm": {
            "provider": cfg.llm.provider,
            "model_name": cfg.llm.model_name,
            "base_url": cfg.llm.base_url,
            "max_context_length": cfg.llm.get("max_context_length"),
            "max_tokens": cfg.llm.get("max_tokens"),
        },
        "agent": {
            "main_agent_max_turns": cfg.agent.main_agent.max_turns,
            "main_agent_tools": list(cfg.agent.main_agent.get("tools") or []),
        },
    }
    logger.info("Effective config (redacted):\n" + OmegaConf.to_yaml(safe_cfg))

    # Create pipeline components using the factory function
    main_agent_tool_manager, sub_agent_tool_managers, output_formatter = (
        create_pipeline_components(cfg)
    )

    # Define task parameters
    task_id = cfg.get("task_id") or "task_example"
    task_description = (
        cfg.get("task_description")
        or "What is the title of today's arxiv paper in computer science?"
    )
    task_file_name = cfg.get("task_file_name") or ""

    # Execute task using the pipeline
    final_summary, final_boxed_answer, log_file_path, _ = await execute_task_pipeline(
        cfg=cfg,
        task_id=task_id,
        task_file_name=task_file_name,
        task_description=task_description,
        main_agent_tool_manager=main_agent_tool_manager,
        sub_agent_tool_managers=sub_agent_tool_managers,
        output_formatter=output_formatter,
        log_dir=cfg.debug_dir,
    )

    logger.info(f"Task completed. log_file_path={log_file_path}")
    if final_boxed_answer:
        logger.info(f"Final boxed answer: {final_boxed_answer}")
    else:
        logger.info("Final boxed answer: <empty>")

    # Print a short human-readable tail for CLI users.
    print("\n--- Result ---")
    print("log:", log_file_path)
    if final_boxed_answer:
        print("boxed:", final_boxed_answer)
    print("summary:")
    print((final_summary or "").strip()[:2000])


@hydra.main(config_path="conf", config_name="config", version_base=None)
def main(cfg: DictConfig) -> None:
    asyncio.run(amain(cfg))


if __name__ == "__main__":
    main()

# Agent Guide (MiroThinker)

Python monorepo built around `uv`, `pytest`, and `ruff`. Use this as the default operating manual for agentic coding agents in this repo.

## Repo Facts

- Runtime: Python (primary packages require `>=3.12`).
- Tools: `uv` (deps/runner), `pytest` (tests), `ruff` (lint+format), `just` (task runner).
- Main code:
  - Agent framework: `apps/miroflow-agent/src/miroflow_agent/`
  - Tooling library: `libs/miroflow-tools/src/miroflow_tools/`
- Layout: `src/`-style packages, built with `hatchling` via per-package `pyproject.toml`.
- Tests:
  - `apps/miroflow-agent/tests/`
  - `libs/miroflow-tools/src/test/`
- Cursor/Copilot rules: no `.cursor/rules/`, no `.cursorrules`, no `.github/copilot-instructions.md` found.

## Setup

```bash
cd apps/miroflow-agent && uv sync
cd libs/miroflow-tools && uv sync
```

Notes:

- Treat `.env` as local-only; never commit secrets.
- Ignore local virtualenvs like `apps/**/.venv/` (do not edit or commit).

## Build / Lint / Format (Root)

```bash
just --list

just precommit      # lint + import sort + mdformat + format
just lint           # ruff check --fix
just sort-imports   # ruff check --select I --fix
just format         # ruff format
just format-md      # mdformat all *.md

just check-license
just insert-license # add headers to staged files
```

File headers:

- Most source files include an Apache-2.0 header (see existing modules under `apps/miroflow-agent/src/` and `libs/miroflow-tools/src/`).
- When adding new files, keep headers consistent; the easiest path is: `git add <files>` then run `just insert-license`.

CI parity (GitHub Actions):

```bash
uv tool run ruff@0.8.0 check --show-fixes --output-format=github
uv tool run ruff@0.8.0 format --diff
```

## Tests

Run tests from the package directory so pytest picks up that package's `pyproject.toml`.

All tests:

```bash
cd apps/miroflow-agent && uv run pytest
cd libs/miroflow-tools && uv run pytest
```

Single test (use `-n 0` to disable xdist parallelism while debugging):

```bash
cd apps/miroflow-agent && uv run pytest tests/test_file.py::test_name -n 0 -v
cd libs/miroflow-tools && uv run pytest src/test/test_manager.py::test_execute_tool_call -n 0 -v
cd apps/miroflow-agent && uv run pytest -k "orchestrator and timeout" -n 0 -v
```

Pytest defaults:

- Both `miroflow-agent` and `miroflow-tools` enable `-n=auto` + coverage + HTML reports via `addopts`.
- Output capture defaults to `--show-capture=stderr` to reduce the chance of leaking sensitive data via logs.
- HTML reports are written to `report.html` (and coverage HTML to `htmlcov/`) in the current package directory.
- For faster iteration: add `--no-cov`, or run `pytest -o addopts='' ...` to override all defaults.

Markers (configured in `libs/miroflow-tools/pyproject.toml`):

```bash
cd libs/miroflow-tools
uv run pytest -m unit
uv run pytest -m integration
uv run pytest -m "not slow"
uv run pytest -m requires_api_key
```

## Running Locally

Main entrypoint (agent framework): `apps/miroflow-agent/main.py`.

Typical workflow:

```bash
cd apps/miroflow-agent
cp .env.example .env
# fill in required keys in .env
uv run python main.py llm=qwen-3 agent=mirothinker_1.7_keep5_max200 llm.base_url=http://localhost:61002/v1
```

Notes:

- `apps/miroflow-agent/conf/agent/` contains pre-configured agent YAMLs.
- Prefer keeping `.env` changes local; add new env vars to `.env.example` when needed.

## Iteration Tips

- If pytest's default `addopts` are too heavy while iterating, run:

```bash
cd apps/miroflow-agent
uv run pytest -o addopts='' -n 0 --no-cov -v
```

- When debugging flaky concurrency issues, keep `-n 0` and consider adding `-x` to stop on first failure.

## Code Style

- Formatting/lint: `ruff` is the source of truth; prefer running `just precommit` over manual edits.
- Ruff config is primarily via CLI (`justfile`); there is no dedicated `ruff.toml` in the repo.
- Markdown: format with `just format-md` (mdformat).
- There is no separate `black`/`isort` configuration; `ruff` covers formatting and import sorting.
- Imports: stdlib, third-party, local; blank line between groups; avoid wildcard imports.
- Types: add type hints on new/modified code; prefer concrete container types; avoid `Any` unless necessary.
- Naming: `snake_case` (files/functions/vars), `PascalCase` (classes), `UPPER_SNAKE_CASE` (constants), leading `_` (private).
- Docstrings: use an Args/Returns style (common in `apps/miroflow-agent/src/core/*`); comment only for non-obvious intent.
- Error handling: raise `ValueError`/`TypeError` for programmer errors; when catching `Exception`, log context (prefer `logger.exception`) and re-raise or return an explicit error result; never log secrets.
- Logging: use module logger `logger = logging.getLogger(__name__)`; keep logs contextual and avoid noisy debug by default.
- Async: much of the code is `asyncio`-driven; avoid blocking the event loop.
- Config: Hydra/OmegaConf via `DictConfig`; prefer `cfg.section.get("key", default)` for optional values.

Optional type checking:

```bash
cd apps/miroflow-agent
uv run pyright
```

## Repo Hygiene

- Do not edit/commit `.env` or secret-like files.
- Avoid editing generated files (especially `uv.lock`) unless dependency changes are required.
- When searching, ignore vendored/virtualenv directories (e.g., `**/.venv/**`).
- Avoid rewriting git history (no `push --force`, no `reset --hard`) unless explicitly required.
- Keep commits focused; avoid mixing formatting-only churn with functional changes.

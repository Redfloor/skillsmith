# skillsmith task runner. Install `just`: https://github.com/casey/just
# Every recipe is a thin wrapper over uv so there's one obvious way to do things.

# Show available recipes.
default:
    @just --list

# One-shot environment bootstrap (works with NO python/node preinstalled).
setup:
    #!/usr/bin/env bash
    if [ "{{os()}}" = "windows" ]; then
        powershell -ExecutionPolicy Bypass -File ./bootstrap.ps1
    else
        bash ./bootstrap.sh
    fi

# Install/refresh deps from the committed lockfile.
sync:
    uv sync --frozen --all-packages

# Audit one or many skills (glob/dir supported by the CLI).
audit path:
    uv run skillsmith audit "{{path}}"

# Evaluate one or many skills (golden + determinism + triggering).
eval path:
    uv run skillsmith eval "{{path}}"

# Run the heal drift-check (snapshot/diff MCP contracts).
heal path:
    uv run skillsmith heal "{{path}}"

# Propose a deterministic-candidate -> script conversion (never auto-commits).
augment path:
    uv run skillsmith augment "{{path}}"

# Full test suite.
test:
    uv run pytest

# Fast lint + type-check (matches CI).
lint:
    uv run ruff check .
    uv run ruff format --check .

typecheck:
    uv run mypy packages

# Auto-fix what ruff can.
fmt:
    uv run ruff check --fix .
    uv run ruff format .

# Everything CI runs, locally.
ci: lint typecheck test

# Serve the docs locally.
docs:
    uv run mkdocs serve

# Regenerate JSON Schemas for the public contracts.
schemas:
    uv run skillsmith schema export --out docs/schemas

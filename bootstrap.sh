#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# skillsmith bootstrap (POSIX) — works on a machine with NO python and NO node.
#
# uv is a single static binary and requires no preinstalled runtime. We use it
# to install a pinned Python, then sync all deps from the committed uv.lock.
# ---------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

note()  { printf '\033[1;36m[skillsmith]\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[skillsmith]\033[0m %s\n' "$*" >&2; }

# 1. Ensure uv is installed (official standalone installer; no runtime needed).
if ! command -v uv >/dev/null 2>&1; then
  note "uv not found — installing via the official installer (https://astral.sh/uv)…"
  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    warn "Neither curl nor wget is available. Install one, or install uv manually:"
    warn "  https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
  fi
  # The installer drops uv in ~/.local/bin (or $XDG_BIN_HOME); make it visible now.
  export PATH="${XDG_BIN_HOME:-$HOME/.local/bin}:$HOME/.cargo/bin:$PATH"
fi
note "uv: $(uv --version)"

# 2. Install the pinned Python interpreter (reads .python-version).
note "Installing pinned Python via uv…"
uv python install

# 3. Install ALL dependencies from the committed lockfile (reproducible).
note "Syncing workspace from uv.lock…"
uv sync --frozen --all-packages || {
  warn "Frozen sync failed (lockfile may be out of date). Falling back to 'uv sync'."
  uv sync --all-packages
}

# 4. Install git pre-commit hooks (best-effort; needs a git repo).
if [ -d .git ] && uv run pre-commit --version >/dev/null 2>&1; then
  note "Installing pre-commit hooks…"
  uv run pre-commit install --install-hooks || warn "pre-commit install skipped."
else
  warn "Skipping pre-commit install (no .git dir or pre-commit unavailable)."
fi

note "Done. Next steps:"
cat <<'EOF'

  uv run skillsmith --help          # explore the CLI
  just audit packages/.../SKILL.md  # audit a skill (or: uv run skillsmith audit <path>)
  just test                         # run the test suite

  Tip: `just setup` re-runs this bootstrap. uv needs no preinstalled runtime.
EOF

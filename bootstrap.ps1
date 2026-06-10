<#
.SYNOPSIS
  skillsmith bootstrap (Windows) — works on a machine with NO python and NO node.

.DESCRIPTION
  uv is a single static binary and requires no preinstalled runtime. We use it to
  install a pinned Python, then sync all deps from the committed uv.lock.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

function Note($msg) { Write-Host "[skillsmith] $msg" -ForegroundColor Cyan }
function Warn($msg) { Write-Host "[skillsmith] $msg" -ForegroundColor Yellow }

# 1. Ensure uv is installed (official standalone installer; no runtime needed).
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Note "uv not found - installing via the official installer (https://astral.sh/uv)..."
    # PowerShell installer per https://docs.astral.sh/uv/getting-started/installation/
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    # Make uv visible in the current session.
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}
Note ("uv: " + (uv --version))

# 2. Install the pinned Python interpreter (reads .python-version).
Note "Installing pinned Python via uv..."
uv python install

# 3. Install ALL dependencies from the committed lockfile (reproducible).
Note "Syncing workspace from uv.lock..."
uv sync --frozen --all-packages
if ($LASTEXITCODE -ne 0) {
    Warn "Frozen sync failed (lockfile may be out of date). Falling back to 'uv sync'."
    uv sync --all-packages
}

# 4. Install git pre-commit hooks (best-effort; needs a git repo).
if ((Test-Path .git) -and (uv run pre-commit --version 2>$null)) {
    Note "Installing pre-commit hooks..."
    try { uv run pre-commit install --install-hooks } catch { Warn "pre-commit install skipped." }
} else {
    Warn "Skipping pre-commit install (no .git dir or pre-commit unavailable)."
}

Note "Done. Next steps:"
@"

  uv run skillsmith --help          # explore the CLI
  just audit packages\...\SKILL.md  # audit a skill (or: uv run skillsmith audit <path>)
  just test                         # run the test suite

  Tip: 'just setup' re-runs this bootstrap. uv needs no preinstalled runtime.
"@ | Write-Host

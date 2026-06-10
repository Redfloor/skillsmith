# skillsmith

> An agent (with subskills) that **audits, optimizes, tests, and self-heals** other
> agentic "skills" and prompt-based tools — starting with the Claude Code
> `SKILL.md` format and the Claude Agent SDK / MCP ecosystem, architected to
> extend to other ecosystems later.

[![CI](https://github.com/redfloor/skillsmith/actions/workflows/ci.yml/badge.svg)](https://github.com/redfloor/skillsmith/actions/workflows/ci.yml)
![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)

---

## Why

Prompt-based tools quietly accrete two problems: **work that should be deterministic
code is left to the model** (burning tokens, adding nondeterminism), and **prompts/
contracts drift** out from under the skills that depend on them. skillsmith treats a
skill the way a good engineering org treats a service — it lints it, evals it,
measures its output variance, and proposes repairs **as reviewable diffs/PRs**, never
silent commits.

## Principles

- **Classify, don't blindly convert.** Each work-block is tagged
  `deterministic-candidate` vs `judgment-required`. Only the former is a candidate
  for code conversion. We never strip out LLM flexibility where judgment is the point.
- **Temperature 0 is necessary-but-insufficient.** Anthropic's API docs note results
  are not fully deterministic even at `temperature: 0.0`. skillsmith prefers
  **structured outputs + JSON-schema validation + deterministic code + empirical
  variance measurement** over relying on temperature alone.
- **Human-in-the-loop by default.** Self-heal flow is
  **detect → diagnose → propose-as-diff/PR → human-approve**, with a full audit
  trail. Auto-fix is opt-in and limited to a low-risk tier (additive/non-breaking
  changes that pass all golden tests). **No silent commits, ever.** This follows
  [OWASP LLM06:2025 Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/).
- **Untrusted by default.** All generated code and all third-party skill code runs in
  a layered sandbox: deny-network, read-only FS, CPU/mem/time limits. Docker alone is
  **not** a security boundary.
- **Parallel & portable.** Audit/eval/heal many skills concurrently, isolated context
  per skill, runs on Linux/macOS/Windows, locally or in CI.

## Quickstart — no preinstalled runtime required

`skillsmith` is bootstrapped by [**uv**](https://docs.astral.sh/uv/), a single static
binary that needs **no preinstalled Python and no Node**. The bootstrap script installs
uv (if missing), uses it to install a pinned Python, and syncs every dependency from the
committed `uv.lock`.

```bash
# macOS / Linux
git clone https://github.com/redfloor/skillsmith && cd skillsmith
./bootstrap.sh           # or: just setup
```

```powershell
# Windows
git clone https://github.com/redfloor/skillsmith; cd skillsmith
./bootstrap.ps1          # or: just setup
```

Then:

```bash
uv run skillsmith --help

# Audit one skill or a whole tree (globs/dirs supported, runs in parallel):
just audit "skills/**/SKILL.md"
uv run skillsmith audit skills/my-skill/SKILL.md --max-parallel 8

# Eval: golden + determinism/variance + triggering accuracy:
just eval skills/my-skill

# Heal: snapshot/diff MCP tool contracts and propose repairs as a PR:
just heal skills/my-skill

# Run skillsmith's own tests:
just test
```

## What each subskill does

| Package | Responsibility |
|---|---|
| `core` | Models, two-layer config (team ceiling + per-dev), sandbox interface, git/PR plumbing, JSON Schema. |
| `adapters` | The `Adapter` protocol + `claude-skill`, `claude-agent-sdk`, `mcp` adapters (others stubbed). |
| `audit` | Parse `SKILL.md`, lint against Anthropic best practices (data-driven), classify work-blocks. |
| `augment` | Generate + wire tested scripts for `deterministic-candidate` blocks. Validates in sandbox, opens a PR. |
| `eval` | Golden/snapshot, regression-vs-baseline, determinism/variance harness, triggering-accuracy tester. |
| `heal` | Snapshot/diff MCP tool contracts, classify severity, detect behavioral drift, propose repairs. |
| `cli` | Typer CLI; bounded-parallel runner; aggregated reporting. |

## Configuration (two layers, human-in-the-loop)

- **`skillsmith.config.yaml`** — committed **team policy**; sets the *ceiling* on
  autonomy per action class (`audit=auto`, `augment=propose`,
  `heal-breaking=propose`, `heal-additive=auto-if-tests-pass`).
- **`skillsmith.local.yaml`** — **gitignored** per-developer preferences and
  remembered choices. May only *tighten* autonomy; the loader clamps anything that
  would exceed the committed ceiling.

See [`docs/self-healing.md`](docs/self-healing.md) for the autonomy tiers and the
reasoning behind human-in-the-loop defaults.

## Documentation

- [Architecture](docs/architecture.md)
- [Extending skillsmith — writing an Adapter](docs/extending.md)
- [Self-healing — autonomy tiers & config](docs/self-healing.md)
- [Future extensions / roadmap](docs/future-extensions.md)

## License

[Apache-2.0](LICENSE).

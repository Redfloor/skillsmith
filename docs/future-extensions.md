# Future extensions / roadmap

skillsmith is architected so that *most* new capability arrives by adding an
**Adapter** (new ecosystem) or a **rule pack / hook** (new analysis) — not by
rewriting the engines. This page is the roadmap and the rationale for the seams
already in place.

## Ecosystem adapters

Shipped: `claude-skill`, `claude-agent-sdk`, `mcp`.

Stubs (interfaces present, `TODO`-marked in `packages/adapters/.../stubs.py`):

| Adapter | What it will map onto core models |
|---|---|
| `openai` | OpenAI Assistants / function-tool schemas + system instructions. |
| `langgraph` | LangGraph node prompts + tool bindings. |
| `crewai` | CrewAI `Agent`/`Task` (role, goal, backstory, tools). |
| `cursor` | `.cursor/rules` and Cursor command/prompt files. |

Each becomes a real adapter by following [Extending](extending.md). Because the engines
are ecosystem-agnostic, audit/eval/augment/heal all light up for free once `discover`
and `parse` exist.

## Analysis & augmentation

- **Model-backed generator for augment.** Today `TemplateGenerator` emits a typed
  skeleton; the pipeline (validate-in-sandbox → variance/token gate → PR) is real. The
  next step is a `Generator` backed by a model that fills in the deterministic logic for
  a `deterministic-candidate` block, behind the same contract (stdin→stdout, nonzero on
  error) so the sandbox validator is unchanged.
- **Semantic frontmatter diffing.** A YAML-aware diff that classifies frontmatter
  changes by meaning (e.g. a `description` reword is a triggering-relevant change) to
  complement the JSON contract diff.
- **DeepEval scored metrics.** The `eval` package's `scored` extra wires DeepEval for
  pytest-native scored metrics; deterministic scorers stay ground truth and
  LLM-as-judge is never the sole gate.
- **promptfoo eval gate in CI.** `ci.yml` carries a promptfoo job; the wrapper already
  refuses configs whose only assertions are LLM-graded.

## Self-healing

- **Live MCP introspection.** `mcp.live_snapshot` currently falls back to the committed
  `*.mcpc.json`. The next step spawns the configured server **inside the sandbox** and
  issues `tools/list` over stdio for a true live contract.
- **Native MCP versioning (SEP-1575 / SEP-1400).** When servers can declare a contract
  version, skillsmith will compare versions directly instead of structurally diffing
  snapshots. The diff module is written so this becomes an additional, preferred code
  path rather than a rewrite.
- **Richer behavioral-drift fingerprinting.** Beyond canary output hashes — structured
  output schema validation and tolerance bands for numeric drift.

## Sandbox

- **Firecracker/microVM path** via microsandbox/e2b for the strongest isolation tier,
  with gVisor and bubblewrap/nsjail as the current layered fallbacks. Backend selection
  and limits are already config-driven (`sandbox.backend_preference`).

## Portability

- The public contracts already emit **JSON Schema** (`skillsmith schema export`), so
  non-Python consumers (dashboards, other-language adapters, CI gates) can integrate
  without importing the Pydantic models. Cross-language adapters are a natural extension.

# Architecture

skillsmith is a **uv workspace monorepo**. Each subskill is its own installable
package under `packages/`, with `core` at the base and `cli` at the top.

```
                +-------------------+
                |        cli        |  Typer app, bounded-parallel runner
                +---------+---------+
                          |
   +----------+-----------+-----------+-----------+
   |          |           |           |           |
+--v--+   +---v---+   +----v---+  +----v---+  +----v---+
|audit|   | eval  |   |augment |  | heal   |  |adapters|
+--+--+   +---+---+   +----+---+  +----+---+  +----+---+
   |          |            |           |           |
   +----------+------------+-----------+-----------+
                          |
                     +----v----+
                     |  core   |  models, config, autonomy, sandbox, git, schema
                     +---------+
```

## Dependency rule

`core` knows nothing about any ecosystem. **Adapters** map a concrete ecosystem
(Claude `SKILL.md`, Claude Agent SDK, MCP) onto core's models. The **engines**
(`audit`, `eval`, `augment`, `heal`) are ecosystem-agnostic — they call
adapter-provided hooks and never hard-code a format. This is what lets a new
ecosystem light up across the whole tool by adding one `Adapter`.

## Data flow (audit example)

1. `cli` expands a glob/dir into work items and fans them out (process pool for the
   CPU-bound static analysis).
2. Each worker loads its **own** `EffectiveConfig` and resolves an `Adapter`
   (isolated context per skill — nothing leaks between skills).
3. The adapter **parses** the target into a `SkillDoc`.
4. The `audit` engine runs the **data-driven linters** (`rules/default.yaml`) plus the
   adapter's own audit hooks, then **classifies** each work-block.
5. Results aggregate into an `AggregateReport` (JSON via Pydantic → JSON Schema) and a
   human summary.

## Key models (`skillsmith_core.models`)

| Model | Purpose |
|---|---|
| `SkillDoc` | Normalized parsed skill (frontmatter + body + companion files). |
| `WorkBlock` | A unit of instruction with its `BlockClassification` + confidence. |
| `Finding` | One lint result (rule id, category, severity, suggestion, evidence). |
| `AuditReport` / `EvalReport` | Structured per-skill outputs. |
| `ContractSnapshot` / `ContractDiff` | MCP tool-contract snapshot + classified drift. |
| `ProposedChange` | A repair delivered as a reviewable diff (never auto-committed). |
| `AuditTrailEntry` | Append-only record of every consequential decision. |

JSON Schemas for the public contracts are emitted by `skillsmith schema export` and
consumed by non-Python tooling.

## Concurrency

- **CPU-bound** static analysis (audit) → `ProcessPoolExecutor`. True parallelism, and
  one skill's crash can't take down the batch.
- **I/O-bound** work (eval/heal — model calls, sandbox spawns) → `asyncio` with a
  bounded `Semaphore` inside a `TaskGroup`.
- `--max-parallel` caps the worker pool for both.

## Trust boundary

All generated code and all third-party skill code is **untrusted** and runs only
inside the [layered sandbox](self-healing.md#sandbox). Docker is a packaging
convenience, **not** a security boundary.

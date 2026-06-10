# Extending skillsmith — writing an Adapter

An **Adapter** teaches skillsmith how to work with a new ecosystem. The engines
(audit/eval/augment/heal) are generic; they only ever talk to adapters. Add one
adapter and the whole tool lights up for that ecosystem.

## The interface

```python
from skillsmith_adapters.base import BaseAdapter, SkillRef, EvalHook, HealHook
from skillsmith_core.models import SkillDoc, Finding

class MyAdapter(BaseAdapter):
    ecosystem = "my-ecosystem"

    def discover(self, root) -> list[SkillRef]:
        """Find targets under `root` (file, dir, or glob root)."""

    def parse(self, ref) -> SkillDoc:
        """Normalize one target into core's SkillDoc."""

    def audit_hooks(self):       # optional: ecosystem-specific lint rules
        return [my_hook]

    def eval_hooks(self, doc):   # optional: how to invoke + score this skill
        return [EvalHook(name="run", invoke=lambda q: ...)]

    def heal_hooks(self, doc):   # optional: contract snapshots for drift detection
        return []
```

Every method except `discover`/`parse` has a no-op default on `BaseAdapter`, so a
minimal adapter only implements those two.

## Registration

Two ways, both supported:

1. **Entry point** (preferred for installed packages) — add to your `pyproject.toml`:

   ```toml
   [project.entry-points."skillsmith.adapters"]
   my-ecosystem = "my_pkg.adapter:MyAdapter"
   ```

2. **Imperative** — call `skillsmith_adapters.register(MyAdapter())` at import time.

`skillsmith adapters` lists everything registered. `detect(path)` auto-selects the
first adapter that can `discover` something at a path.

## What each hook feeds

- **`audit_hooks`** run *in addition to* the generic data-driven linter. Use them for
  rules unique to your format (e.g. the `claude-skill` adapter checks for an
  unenforced JSON output contract).
- **`eval_hooks`** provide an `invoke(query) -> str` the determinism/golden harness
  calls N times. Implement it to run inside the sandbox. Optionally provide
  `should_trigger` / `should_not_trigger` queries for the triggering-accuracy tester.
- **`heal_hooks`** provide a `snapshot() -> ContractSnapshot` for drift detection plus
  optional `canary_queries` for behavioral-drift fingerprinting.

## Worked reference

The shipped adapters are the best examples:

- `packages/adapters/src/skillsmith_adapters/claude_skill.py` — full parse + audit hooks.
- `packages/adapters/src/skillsmith_adapters/mcp.py` — snapshot/heal hooks.
- `packages/adapters/src/skillsmith_adapters/stubs.py` — the shape of a not-yet-built
  adapter (OpenAI / LangGraph / CrewAI / Cursor). Turning a stub into a real adapter is
  exactly this guide.

## Testing your adapter

Drop a fixture skill under `tests/fixtures/` with an `expected.yaml` manifest of the
issues it should surface, and the existing meta-eval (`tests/test_meta_eval.py`) will
exercise it automatically.

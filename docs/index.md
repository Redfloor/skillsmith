# skillsmith

An agent (with subskills) that **audits, optimizes, tests, and self-heals** other
agentic skills and prompt-based tools — starting with the Claude Code `SKILL.md`
format and the Claude Agent SDK / MCP ecosystem, architected to extend elsewhere.

- **[Architecture](architecture.md)** — packages, data flow, the `Adapter` boundary.
- **[Extending](extending.md)** — write an `Adapter` for a new ecosystem.
- **[Self-healing](self-healing.md)** — autonomy tiers, config, why human-in-the-loop.
- **[Future extensions](future-extensions.md)** — the roadmap.

## The one-paragraph pitch

skillsmith reads a skill, **classifies each work-block** as `deterministic-candidate`
or `judgment-required`, and only ever offers to convert the former into a tested
script — cutting tokens and nondeterminism without stripping out judgment where it
matters. It treats `temperature: 0` as necessary-but-insufficient and **measures
output variance empirically**. Every repair it proposes flows through
**detect → diagnose → propose-as-diff/PR → human-approve**, with a full audit trail
and a layered sandbox around all untrusted code. No silent commits, ever.

## Install & run (no preinstalled runtime)

```bash
./bootstrap.sh          # installs uv, a pinned Python, and all deps from uv.lock
uv run skillsmith --help
```

See the [README](https://github.com/redfloor/skillsmith#readme) for the full quickstart.

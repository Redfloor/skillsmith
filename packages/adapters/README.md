# skillsmith-adapters

The portability layer. Every ecosystem skillsmith supports is reached through one
`Adapter`:

```
discover(root)   -> [SkillRef ...]      # find targets
parse(ref)       -> SkillDoc            # normalize into core models
audit_hooks()    -> [AuditHook ...]     # ecosystem-specific lint rules
eval_hooks()     -> [EvalHook ...]      # how to invoke + score this skill
heal_hooks()     -> [HealHook ...]      # contract snapshot/diff providers
```

Shipped adapters: `claude-skill`, `claude-agent-sdk`, `mcp`.
Stubs (with TODOs): `openai`, `langgraph`, `crewai`, `cursor`.

See [`docs/extending.md`](../../docs/extending.md) to write your own.

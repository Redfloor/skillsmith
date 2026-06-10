# Self-healing — autonomy tiers, config, and why human-in-the-loop is the default

skillsmith can repair drift and optimize skills. It does so **conservatively, on
purpose**. The default flow is:

> **detect → diagnose → propose-as-diff/PR → human-approve**, with a full audit trail.

Auto-fix is **opt-in** and limited to a low-risk tier (additive/non-breaking changes
that pass all golden tests). **No silent commits, ever.**

## Why human-in-the-loop is the default

This follows [OWASP **LLM06:2025 Excessive Agency**](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)
and the OWASP Agentic Top 10 reasoning: an autonomous agent with broad permissions and
imperfect judgment is a liability. The mitigations skillsmith adopts directly:

- **Require human approval for high-impact actions.** Breaking changes and code
  generation are pinned to human review (`approval_gates.require_human`).
- **Avoid open-ended capabilities.** Raw shell execution and sandbox network egress are
  in `approval_gates.forbid` and cannot be enabled by local config.
- **Least privilege + full traceability.** Every decision is written to an append-only
  audit trail (`.skillsmith/audit-trail.jsonl`), and every change ships as a branch+PR
  so a human reviews the diff before anything merges.

Descriptions get special treatment: an MCP tool **description change is a `warning`,
not cosmetic**, because descriptions are model instructions — reworded text can
silently change behavior.

## Autonomy tiers (per action class)

| Tier | Meaning |
|---|---|
| `auto` | Apply without asking (only ever sane for read-only `audit`). |
| `auto-if-tests-pass` | Apply automatically **iff** all golden tests pass **and** the change is additive/non-breaking (the low-risk tier). |
| `propose` | Open a PR with a diff + audit-trail entry; a human approves. |
| `off` | Never perform this action class. |

The single decision chokepoint is `skillsmith_core.autonomy.decide(...)`; every
actuator routes through it.

## Two-layer config

```
skillsmith.config.yaml   (committed)  -> TEAM POLICY = the autonomy CEILING
skillsmith.local.yaml    (gitignored) -> per-developer prefs + remembered choices
```

The committed policy sets the **ceiling**. The local file may only ever *tighten*
autonomy; the loader **clamps** any local value that would exceed the ceiling
(`clamp()` picks the more-restrictive tier). The first time a heal/augment decision is
hit, skillsmith prompts for *auto-fix vs propose-and-approve* and persists the answer to
the local file — still clamped to the team ceiling.

Example team policy:

```yaml
autonomy:
  audit: auto
  augment: propose
  heal_additive: auto-if-tests-pass
  heal_breaking: propose
  heal_warning: propose
approval_gates:
  require_human: [heal_breaking, augment]
  forbid: [raw_shell_execution, network_egress_from_sandbox]
```

## MCP contract drift

1. **Snapshot** each server's tool contract (names, params, input schemas,
   descriptions) to a committed `*.mcpc.json` artifact.
2. **Diff** on demand / in CI (`drift-check.yml`) and **classify severity**:
   - added / added-optional → `info`
   - removed / renamed / required-added / type-changed → **breaking** (`error`)
   - description changed → `warning`
3. **Behavioral drift** — run canary queries and fingerprint the outputs, so a server
   that changed behavior without changing its schema is still caught.
4. **Propose** a repair (updated snapshot + dependent skill edits) per the autonomy
   policy, with an audit-trail entry.

> **Future:** [SEP-1575 / SEP-1400](https://modelcontextprotocol.io) propose native MCP
> capability/contract versioning. When servers can declare a contract version,
> skillsmith will compare versions directly instead of structurally diffing snapshots.
> Until then, snapshot+diff is the source of truth (see `packages/heal/.../diff.py`).

## Sandbox

All generated and third-party code runs in a **layered** sandbox, strongest-available
first:

```
firecracker (microVM) > gvisor (runsc) > bubblewrap > nsjail > none
```

Defaults under the `strict` profile: **deny network, read-only FS, CPU/memory/wall
limits**. If no isolating backend is available, the `strict` profile **refuses to run**
rather than executing untrusted code unprotected. Docker alone is **not** a security
boundary and is never used as a backend.

## Augment gating

A `deterministic-candidate` → script proposal is only emitted when the generated script
(a) passes the skill's golden tests **inside the sandbox**, (b) has output variance
**equal-or-better** than the prose it replaces, and (c) yields a **meaningful token
reduction**. Even then it is a branch+PR — the autonomy policy decides whether the
low-risk tier may auto-apply.

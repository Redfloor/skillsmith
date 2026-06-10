# skillsmith-augment

For `deterministic-candidate` work-blocks (and helpers regenerated across runs),
augment generates a script (Python/bash), wires it into the skill's `scripts/`, and
updates `SKILL.md` to call it.

**Guardrails (enforced, not aspirational):**
- Validates the script in the **sandbox** against the skill's golden tests.
- Opens a PR **only if** it passes with **equal-or-better output variance** *and* a
  **meaningful token reduction**.
- **Never auto-commits.** Output is always a branch + PR for human approval.

The codegen step itself is stubbed (the model-backed generator is wired behind a
`Generator` protocol); the validation/gating/PR plumbing is real.

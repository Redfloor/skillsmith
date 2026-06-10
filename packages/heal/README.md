# skillsmith-heal

Self-healing for MCP-dependent skills, **human-in-the-loop by default**.

1. **Snapshot** each target's MCP server tool contract (names, params, input schemas,
   descriptions) to a committed `*.mcpc.json` artifact.
2. **Diff** on demand / in CI by re-fetching and comparing. Severity classification:
   - added-optional → **info**
   - removed / renamed / required-added / type-changed → **breaking**
   - description changed → **warning** (descriptions are model instructions, so a
     wording change can silently alter behavior)
3. On drift, run **canary queries + output fingerprinting** to catch *behavioral*
   (not just schema) drift.
4. **Autonomy policy** (`skillsmith_core.autonomy.decide`): by default open a PR with
   a proposed repair + the diff + an audit-trail entry. The first time a heal/augment
   decision is hit, prompt for auto-fix vs propose-and-approve and persist the answer
   (clamped to the team ceiling).

> Future: native MCP versioning per **SEP-1575 / SEP-1400** would let servers declare
> contract versions; until then we snapshot and diff. (See comments in `diff.py`.)

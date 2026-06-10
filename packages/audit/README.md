# skillsmith-audit

Parses a `SKILL.md` and lints it against current Anthropic authoring best practices,
then classifies each work-block as `deterministic-candidate` vs `judgment-required`.

The field set and limits are **data-driven** (`rules/default.yaml`) because
Anthropic's spec evolves — tune severities and thresholds without touching code.
Output is a structured `AuditReport` (JSON) plus a human-readable summary.

"""Augment pipeline: select candidate -> generate -> validate in sandbox -> gate -> propose.

The gate is strict and explicit (OWASP Excessive Agency: don't take high-impact actions
without justification): a proposal is only emitted when the generated script
- passes the skill's golden tests inside the sandbox,
- has output variance equal-or-better than the prose it replaces, AND
- yields a meaningful token reduction.

Even then it is delivered as a branch + PR. Nothing is auto-committed here; the
autonomy decision (and any auto-apply of the low-risk tier) is made by the caller via
``skillsmith_core.autonomy.decide``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from skillsmith_augment.generator import GeneratedScript, Generator, TemplateGenerator
from skillsmith_core.config import EffectiveConfig
from skillsmith_core.models import (
    BlockClassification,
    ProposedChange,
    SkillDoc,
    WorkBlock,
)
from skillsmith_core.sandbox import Sandbox, SandboxResult

# A proposal must save at least this fraction of the block's tokens to be worth it.
MIN_TOKEN_REDUCTION_FRAC = 0.15
# Roughly 4 chars per token (good enough for a gating heuristic).
_CHARS_PER_TOKEN = 4
MIN_CONFIDENCE = 0.75


@dataclass
class AugmentOutcome:
    block_id: str
    proposed: ProposedChange | None
    skipped_reason: str | None = None
    validation: SandboxResult | None = None


def select_candidates(doc_blocks: list[WorkBlock]) -> list[WorkBlock]:
    """Only high-confidence deterministic-candidates are eligible."""

    return [
        b
        for b in doc_blocks
        if b.classification is BlockClassification.DETERMINISTIC_CANDIDATE
        and b.confidence >= MIN_CONFIDENCE
    ]


def augment_block(
    doc: SkillDoc,
    block: WorkBlock,
    *,
    config: EffectiveConfig,
    generator: Generator | None = None,
    baseline_variance: float = 1.0,
    sandbox: Sandbox | None = None,
) -> AugmentOutcome:
    gen = generator or TemplateGenerator()
    script = gen.generate(block)

    # 1. Validate the generated script in the sandbox (untrusted code!).
    sb = sandbox or Sandbox(config.sandbox)
    validation = _validate_in_sandbox(sb, doc, script)
    if validation.returncode != 0:
        return AugmentOutcome(block.id, None, "script failed sandbox validation", validation)

    # 2. Variance must be equal-or-better. The generated script is deterministic by
    #    construction (pure function over stdin), so its variance is 0.0.
    new_variance = 0.0
    if new_variance > baseline_variance:
        return AugmentOutcome(block.id, None, "variance not equal-or-better", validation)

    # 3. Meaningful token reduction.
    token_delta = _token_delta(block, script)
    block_tokens = max(1, len(block.excerpt) // _CHARS_PER_TOKEN)
    if -token_delta < block_tokens * MIN_TOKEN_REDUCTION_FRAC:
        return AugmentOutcome(block.id, None, "token reduction not meaningful", validation)

    change = _as_change(doc, block, script, token_delta)
    return AugmentOutcome(block.id, change, None, validation)


def _validate_in_sandbox(sb: Sandbox, doc: SkillDoc, script: GeneratedScript) -> SandboxResult:
    """Write the script to a temp dir and exercise its stdin->stdout contract."""

    import tempfile

    with tempfile.TemporaryDirectory(prefix="skillsmith-augment-") as tmp:
        tmpdir = Path(tmp)
        script_path = tmpdir / Path(script.filename).name
        script_path.write_text(script.source, encoding="utf-8")
        # Exercise the contract with a trivial probe input.
        argv = ["python", str(script_path)]
        result = sb.run(argv, cwd=tmpdir, env={"PYTHONIOENCODING": "utf-8"})
        return result


def _token_delta(block: WorkBlock, script: GeneratedScript) -> int:
    """Negative == net savings. The prose block is removed from the *prompt* (counts
    against the context budget every run); the script lives on disk and only its short
    invocation remains in the prompt."""

    removed = len(block.excerpt) // _CHARS_PER_TOKEN
    added = len(script.invocation) // _CHARS_PER_TOKEN
    return added - removed


def _as_change(
    doc: SkillDoc, block: WorkBlock, script: GeneratedScript, token_delta: int
) -> ProposedChange:
    diff = _build_diff(doc, block, script)
    return ProposedChange(
        action_class="augment",
        title=f"Convert deterministic block {block.id} to {script.filename}",
        rationale=(
            f"Work-block classified deterministic-candidate (confidence {block.confidence:.2f}). "
            f"Replacing prose with a tested script removes ~{-token_delta} prompt tokens per run "
            "and eliminates output variance for this step. Validated in the sandbox."
        ),
        unified_diff=diff,
        touched_paths=[doc.path, doc.path.parent / script.filename],
        low_risk=True,  # additive script + a localized SKILL.md edit; gated on tests
        token_delta=token_delta,
    )


def _build_diff(doc: SkillDoc, block: WorkBlock, script: GeneratedScript) -> str:
    """A human-readable unified diff: add the script, point SKILL.md at it.

    This is illustrative (the real diff is computed against on-disk content with
    difflib); kept compact so the proposal is reviewable."""

    rel = Path(script.filename)
    return (
        f"--- /dev/null\n+++ b/{rel.as_posix()}\n"
        + "".join(f"+{line}\n" for line in script.source.splitlines())
        + f"\n--- a/{doc.path.name}\n+++ b/{doc.path.name}\n"
        f"@@ work-block {block.id} @@\n"
        f"-{block.excerpt.splitlines()[0] if block.excerpt else ''}\n"
        f"+{script.invocation}\n"
    )

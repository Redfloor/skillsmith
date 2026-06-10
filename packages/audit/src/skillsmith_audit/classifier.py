"""Classify each work-block: deterministic-candidate vs judgment-required.

This is skillsmith's most opinionated step and the gate in front of augment. We
score each block on signals from the data-driven ruleset; deterministic signals add,
judgment signals subtract. Only HIGH-confidence deterministic-candidates are ever
offered for code conversion. We never strip out LLM flexibility where judgment is
the point — judgment-required blocks are surfaced, never converted.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from skillsmith_core.models import (
    BlockClassification,
    Location,
    SkillDoc,
    WorkBlock,
)

# Split the body into candidate work-blocks: numbered/bulleted steps and paragraphs.
_STEP_RE = re.compile(r"^\s*(?:\d+\.|[-*+])\s+", re.MULTILINE)


def classify(doc: SkillDoc, classifier_cfg: dict[str, Any]) -> list[WorkBlock]:
    threshold = classifier_cfg.get("threshold", 2)
    det_weights = classifier_cfg.get("deterministic_signals", {})
    jud_weights = classifier_cfg.get("judgment_signals", {})
    det_keywords = classifier_cfg.get("deterministic_keywords", {})
    jud_keywords = classifier_cfg.get("judgment_keywords", {})

    blocks: list[WorkBlock] = []
    for idx, (text, line) in enumerate(_iter_blocks(doc.body)):
        low = text.lower()
        score = 0
        signals: list[str] = []

        for group, kws in det_keywords.items():
            if any(k in low for k in kws):
                w = det_weights.get(group, 1)
                score += w
                signals.append(f"+{group}({w})")
        for group, kws in jud_keywords.items():
            if any(k in low for k in kws):
                w = jud_weights.get(group, -1)
                score += w
                signals.append(f"{group}({w})")

        is_det = score >= threshold
        classification = (
            BlockClassification.DETERMINISTIC_CANDIDATE
            if is_det
            else BlockClassification.JUDGMENT_REQUIRED
        )
        confidence = _confidence(score, threshold)
        rationale = _rationale(is_det, signals, score, threshold)
        blocks.append(
            WorkBlock(
                id=f"{doc.name or doc.path.stem}#b{idx}",
                location=Location(path=doc.path, line=line),
                excerpt=text.strip()[:240],
                classification=classification,
                rationale=rationale,
                confidence=confidence,
                signals=signals,
            )
        )
    return blocks


def _iter_blocks(body: str) -> Iterator[tuple[str, int]]:
    """Yield (text, start_line) for each step/paragraph block."""

    lines = body.splitlines()
    # Prefer explicit steps; fall back to paragraph splitting.
    if _STEP_RE.search(body):
        current: list[str] = []
        start = 1
        for i, line in enumerate(lines, start=1):
            if _STEP_RE.match(line) and current:
                yield "\n".join(current), start
                current = [line]
                start = i
            else:
                if not current:
                    start = i
                current.append(line)
        if current and "".join(current).strip():
            yield "\n".join(current), start
        return

    para: list[str] = []
    start = 1
    for i, line in enumerate(lines, start=1):
        if not line.strip():
            if para:
                yield "\n".join(para), start
                para = []
        else:
            if not para:
                start = i
            para.append(line)
    if para:
        yield "\n".join(para), start


def _confidence(score: int, threshold: int) -> float:
    # Distance from the threshold maps to confidence; clamp to [0.5, 0.99].
    distance = abs(score - threshold)
    return max(0.5, min(0.99, 0.5 + 0.12 * distance))


def _rationale(is_det: bool, signals: list[str], score: int, threshold: int) -> str:
    sig = ", ".join(signals) if signals else "no strong signals"
    if is_det:
        return (
            f"Scored {score} (>= {threshold}); signals [{sig}] indicate deterministic, "
            "mechanical work (parse/convert/compute) that could become a tested script."
        )
    return (
        f"Scored {score} (< {threshold}); signals [{sig}] indicate judgment is required. "
        "Left to the model — converting would strip out flexibility where it matters."
    )

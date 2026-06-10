"""Script generation behind a swappable protocol.

The real generator is model-backed (it reads a deterministic-candidate work-block and
emits a small, single-purpose script). That part is intentionally pluggable so the
augment *pipeline* — validate-in-sandbox + gate + PR — can be tested with a stub
generator and so different backends (Claude, a local model, a template library) can
be slotted in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from skillsmith_core.models import WorkBlock


@dataclass(frozen=True)
class GeneratedScript:
    filename: str  # e.g. "scripts/extract_fields.py"
    language: str  # "python" | "bash"
    source: str
    # How SKILL.md should invoke it, to replace the prose work-block.
    invocation: str


class Generator(Protocol):
    def generate(self, block: WorkBlock) -> GeneratedScript: ...


class TemplateGenerator:
    """Stub generator: emits a typed, single-purpose Python skeleton with a TODO.

    Real generation (model-backed) replaces the body; the contract — stdin in, stdout
    out, nonzero exit on error — stays fixed so the sandbox validator is stable.
    """

    def generate(self, block: WorkBlock) -> GeneratedScript:
        filename = f"scripts/{_safe(block.id)}.py"
        source = _PY_TEMPLATE.format(block_id=block.id, excerpt=block.excerpt.replace("\n", " "))
        invocation = f"Run `python {filename}` (reads input on stdin, writes result to stdout)."
        return GeneratedScript(
            filename=filename, language="python", source=source, invocation=invocation
        )


def _safe(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text).strip("_").lower() or "step"


_PY_TEMPLATE = '''\
#!/usr/bin/env python3
"""Deterministic replacement for work-block {block_id}.

Auto-proposed by skillsmith. Contract: read input on stdin, write result to stdout,
exit nonzero on error. Reviewed by a human before merge.

Original prose this replaces:
    {excerpt}
"""
from __future__ import annotations

import sys


def transform(data: str) -> str:
    # TODO(skillsmith): the model-backed generator fills in the deterministic logic
    # for this block. The template echoes input so the sandbox validator has a stable,
    # non-crashing contract to exercise until the real body lands.
    return data


def main() -> int:
    try:
        sys.stdout.write(transform(sys.stdin.read()))
    except Exception as exc:  # noqa: BLE001 - scripts must fail loud, not silent
        print(f"error: {{exc}}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

#!/usr/bin/env python3
"""Deterministically normalize a CSV read on stdin; write cleaned CSV to stdout.

This is the kind of mechanical, reproducible work skillsmith wants in a script
rather than in the prompt: parse + dedupe + sort, no judgment required.
"""

from __future__ import annotations

import csv
import io
import sys


def normalize(text: str) -> str:
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    header, *body = rows if rows else ([],)
    seen: set[tuple[str, ...]] = set()
    deduped = []
    for row in body:
        key = tuple(c.strip() for c in row)
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    deduped.sort(key=lambda r: r[0] if r else "")
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    if header:
        writer.writerow(header)
    writer.writerows(deduped)
    return out.getvalue()


def main() -> int:
    try:
        sys.stdout.write(normalize(sys.stdin.read()))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

---
name: csv-cleaner
description: Cleans messy CSV files into a normalized schema. Use this when the user
  has a .csv with malformed rows, inconsistent headers, or junk lines and wants a
  tidy spreadsheet out. Not for Excel-specific formatting.
---

# CSV Cleaner

Use this when the user provides a messy CSV and wants it normalized.

1. Run `python scripts/normalize.py` to parse the CSV and deduplicate rows
   deterministically. If it exits nonzero, report the error and stop.
2. Validate the result against the schema in [schema.json](reference/schema.json)
   so the output contract is enforced, otherwise the downstream step will reject it.
3. If the user asks, explain which rows were dropped and why — this needs judgment
   about what counts as "junk" for their data.

See [the format guide](reference/format.md) for column conventions.

# Column conventions

- `id` — stable unique key (string).
- `name` — display name (string).
- `amount` — numeric; blanks become `0`.

Rows missing `id` are treated as junk and dropped.

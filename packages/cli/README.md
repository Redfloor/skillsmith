# skillsmith-cli

The `skillsmith` command. Subcommands: `audit`, `eval`, `heal`, `augment`,
`schema`, `adapters`. Each accepts a file, directory, or glob and processes many
skills **concurrently** with a bounded worker pool (`--max-parallel`), isolated
context per skill, and aggregated reporting.

CPU-bound static analysis (audit) runs on a `ProcessPoolExecutor`; LLM/eval I/O uses
`asyncio` with bounded `TaskGroup`s.

# Changelog

All notable changes to skillsmith are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Release notes are written intentionally (Changesets-style): each user-facing
change adds an entry under **Unreleased**, and `release.yml` rolls them into a
versioned section on publish.

## [Unreleased]

### Added
- Initial uv workspace monorepo scaffold (`packages/{core,adapters,audit,augment,eval,heal,cli}`).
- `core`: Pydantic v2 models, two-layer config loader with autonomy-ceiling clamping,
  layered sandbox interface, and branch+PR git plumbing.
- `adapters`: `Adapter` protocol and `claude-skill`, `claude-agent-sdk`, `mcp` adapters;
  stubs for OpenAI / LangGraph / CrewAI / Cursor.
- `audit`: SKILL.md parser + data-driven linter, deterministic-candidate classifier,
  JSON + human-readable reports.
- `eval` (MVP): golden/snapshot, regression-vs-baseline, determinism/variance harness,
  triggering-accuracy tester with train/held-out split, promptfoo wrapper.
- `augment` / `heal`: working interfaces with sandbox + git-PR plumbing (implementation stubbed).
- `cli`: Typer app with parallel runner (`--max-parallel`) and aggregated reporting.
- Bootstrap that works with no preinstalled Python/Node (`bootstrap.sh`, `bootstrap.ps1`).
- CI (`ci.yml`), scheduled MCP drift checks (`drift-check.yml`), release automation (`release.yml`).
- Docs: architecture, extending (Adapters), self-healing (autonomy tiers), future extensions.

[Unreleased]: https://github.com/redfloor/skillsmith/compare/HEAD

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
SKILLS = FIXTURES / "skills"
MCP = FIXTURES / "mcp"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def skills_dir() -> Path:
    return SKILLS


@pytest.fixture
def mcp_dir() -> Path:
    return MCP


def all_skill_fixtures() -> list[Path]:
    return sorted(SKILLS.glob("*/SKILL.md"))

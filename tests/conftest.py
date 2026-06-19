"""Shared test helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    """Return a JSON fixture loader."""

    def _load(name: str) -> dict[str, Any]:
        with (FIXTURES / name).open(encoding="utf-8") as fixture:
            data = json.load(fixture)
        assert isinstance(data, dict)
        return data

    return _load

"""Static seed data for the Discovery and Career agents.

`programs.json` and `careers.json` are the grounding sources the agents cite from
(see Risk 1 in RFC §8 — every factual claim should reference a record id).

`learners.json` powers the StubCRMClient so the orchestrator can run end-to-end
without a HubSpot account.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).parent


def _load(name: str) -> list[dict[str, Any]]:
    with (_DATA_DIR / name).open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def programs() -> list[dict[str, Any]]:
    return _load("programs.json")


@lru_cache
def careers() -> list[dict[str, Any]]:
    return _load("careers.json")


@lru_cache
def learners() -> list[dict[str, Any]]:
    return _load("learners.json")

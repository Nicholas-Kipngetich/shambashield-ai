"""Loader for the farmer-messaging phrasebook (data/messages.yaml)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .contracts import Language

_MESSAGES_FILE = Path(__file__).parent / "data" / "messages.yaml"


@lru_cache(maxsize=1)
def load_phrasebook() -> dict[str, dict[str, Any]]:
    """Return {language: {section: templates}}; falls back to English."""
    with _MESSAGES_FILE.open(encoding="utf-8") as file:
        raw: dict[str, Any] = yaml.safe_load(file)
    return {lang: payload for lang, payload in raw.items() if lang in ("en", "sw")}


def templates_for(language: str) -> dict[str, Any]:
    book = load_phrasebook()
    return book.get(language) or book["en"]


def supported_languages() -> list[str]:
    return sorted(load_phrasebook())


def translation_status(language: str, requested: Language) -> str:
    """Human-readable note when the requested language lacks drafts."""
    if language == requested:
        return ""
    return "The requested language is not drafted yet; English summary shown."

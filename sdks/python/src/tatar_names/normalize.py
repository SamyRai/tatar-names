"""Normalization keys for names, at three explicit levels.

Each level answers a different question; callers must pick the level whose
contract they rely on:

- ``Level.CANONICAL``: the recorded form itself, NFC-normalized. Preserves
  case, letters and punctuation; it is NOT a lookup key.
- ``Level.LOOKUP``: the exact-match key implemented by ``safe()``. Stable
  across dataset versions: a record's lookup key never changes when the
  dataset is re-released.
- ``Level.CANDIDATE_SEARCH``: the lossy candidate key implemented by
  ``soft_key()``. May change with rule releases and must never be used as
  proof that two names are the same.

Fuzzy matching is not a normalization level. It happens in the resolver on
top of candidate keys; ``normalize_key`` never returns fuzzy results.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from enum import Enum

_PUNCTUATION_RE = re.compile(r"[.,/#!$%^&*;:{}=_`~()]")
_HYPHENS_RE = re.compile(r"[‐‑‒–—−]")
_SPACE_RE = re.compile(r"\s+")


class Level(str, Enum):
    """Normalization levels; see the module docstring for each contract."""

    CANONICAL = "canonical"
    LOOKUP = "lookup"
    CANDIDATE_SEARCH = "candidate_search"


def _canonical(name: str) -> str:
    return unicodedata.normalize("NFC", name)


def safe(name: str) -> str:
    """Return a reversible-enough lookup key for exact matching."""
    if not name:
        return ""
    value = unicodedata.normalize("NFKC", name).lower().strip()
    value = value.replace("ё", "е")
    value = _HYPHENS_RE.sub("-", value)
    value = _PUNCTUATION_RE.sub("", value)
    return _SPACE_RE.sub(" ", value)


def soft_key(name: str) -> str:
    """Return a lossy key for candidate generation only."""
    return safe(name).replace("й", "и").translate(str.maketrans("", "", "ьъ'\"- "))


_LEVEL_KEYS: dict[Level, Callable[[str], str]] = {
    Level.CANONICAL: _canonical,
    Level.LOOKUP: safe,
    Level.CANDIDATE_SEARCH: soft_key,
}


def normalize_key(name: str, level: Level) -> str:
    """Return the key for ``name`` at the requested level."""
    try:
        key = _LEVEL_KEYS[Level(level)]
    except ValueError:
        raise ValueError(f"Unknown normalization level: {level}") from None
    return key(name)

from __future__ import annotations

import re
import unicodedata

_PUNCTUATION_RE = re.compile(r"[.,/#!$%^&*;:{}=_`~()]")
_HYPHENS_RE = re.compile(r"[‐‑‒–—−]")
_SPACE_RE = re.compile(r"\s+")


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

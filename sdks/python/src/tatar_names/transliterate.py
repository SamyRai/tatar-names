"""Deterministic Cyrillic-to-Latin transliteration profiles.

Profiles are interchangeable at the call site but not at the contract level:
each carries a ``ProfileContract`` declaring its purpose and limits. None of
these profiles is a legal transliteration authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from .data import rules_path

ProfilePurpose = Literal["search_candidate", "documentary_candidate"]

PROFILE_FILES = {
    # "rt2013" is a historical id: this map is a lossy ASCII search fold
    # (ә/а, ө/о, ү/у, ң/н collapse onto one letter), not the RT-2013 legal annex.
    "tt_cyrl_to_tt_latn_rt2013": "transliteration_tt_latn.yaml",
    "ru_cyrl_to_latn_mvd_doc": "transliteration_ru_latn_passport.yaml",
}


def _load_simple_yaml_map(filename: str) -> dict[str, str]:
    path = rules_path(filename)
    mapping: dict[str, str] = {}
    in_map = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line == "map:":
            in_map = True
            continue
        if not in_map or not line.startswith("  "):
            continue
        key, value = line.strip().split(":", 1)
        value = value.strip()
        if value == '""':
            value = ""
        mapping[key] = value
    return mapping


@dataclass(frozen=True)
class ProfileContract:
    """What a transliteration profile guarantees; see docs/transliteration.md."""

    profile_id: str
    purpose: ProfilePurpose
    lossy: bool
    legal_authority: bool
    notes: str


_PROFILE_CONTRACTS: tuple[ProfileContract, ...] = (
    ProfileContract(
        profile_id="tt_cyrl_to_tt_latn_rt2013",
        purpose="search_candidate",
        lossy=True,
        legal_authority=False,
        notes=(
            "Lossy ASCII search fold: ә/а, ө/о, ү/у, ң/н collapse onto one "
            "letter. The id is historical; this is not the RT-2013 legal annex."
        ),
    ),
    ProfileContract(
        profile_id="ru_cyrl_to_latn_mvd_doc",
        purpose="documentary_candidate",
        lossy=True,
        legal_authority=False,
        notes=(
            "Passport-style documentary approximations (kh/ts/shch) for "
            "candidate generation, not a legal transliteration authority."
        ),
    ),
)


def profiles() -> tuple[ProfileContract, ...]:
    """Return the declared contract of every available profile."""
    return _PROFILE_CONTRACTS


def available_profiles() -> tuple[str, ...]:
    return tuple(contract.profile_id for contract in _PROFILE_CONTRACTS)


@lru_cache(maxsize=None)
def profile_map(profile: str) -> dict[str, str]:
    if profile not in PROFILE_FILES:
        raise ValueError(f"Unknown transliteration profile: {profile}")
    return _load_simple_yaml_map(PROFILE_FILES[profile])


def _apply_map(value: str, mapping: dict[str, str]) -> str:
    parts: list[str] = []
    for index, char in enumerate(value):
        lower = char.lower()
        mapped = mapping.get(lower, char)
        if char.isupper() and mapped:
            # Casing is run-aware: mid-run mappings go full uppercase so
            # multi-letter maps stay TSAR-shaped; the run's last mapping
            # capitalizes as before.
            next_is_upper = index + 1 < len(value) and value[index + 1].isupper()
            parts.append(mapped.upper() if next_is_upper else mapped.capitalize())
        else:
            parts.append(mapped)
    return "".join(parts)


def transliterate(value: str, profile: str) -> str:
    return _apply_map(value, profile_map(profile))


def ru_to_latin(value: str) -> str:
    return transliterate(value, "ru_cyrl_to_latn_mvd_doc")


def tt_to_latin(value: str) -> str:
    return transliterate(value, "tt_cyrl_to_tt_latn_rt2013")

from __future__ import annotations

from functools import lru_cache

from .data import project_root

PROFILE_FILES = {
    "tt_cyrl_to_tt_latn_rt2013": "transliteration_tt_latn.yaml",
    "ru_cyrl_to_latn_mvd_doc": "transliteration_ru_latn_passport.yaml",
}


def _load_simple_yaml_map(filename: str) -> dict[str, str]:
    path = project_root() / "rules" / filename
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


def available_profiles() -> tuple[str, ...]:
    return tuple(PROFILE_FILES)


@lru_cache(maxsize=None)
def profile_map(profile: str) -> dict[str, str]:
    if profile not in PROFILE_FILES:
        raise ValueError(f"Unknown transliteration profile: {profile}")
    return _load_simple_yaml_map(PROFILE_FILES[profile])


def _apply_map(value: str, mapping: dict[str, str]) -> str:
    parts: list[str] = []
    for char in value:
        lower = char.lower()
        mapped = mapping.get(lower, char)
        parts.append(mapped.capitalize() if char.isupper() and mapped else mapped)
    return "".join(parts)


def transliterate(value: str, profile: str) -> str:
    return _apply_map(value, profile_map(profile))


def ru_to_latin(value: str) -> str:
    return transliterate(value, "ru_cyrl_to_latn_mvd_doc")


def tt_to_latin(value: str) -> str:
    return transliterate(value, "tt_cyrl_to_tt_latn_rt2013")

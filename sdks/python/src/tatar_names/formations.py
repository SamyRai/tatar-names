from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


PATRONYMIC_SUFFIXES = {
    "male": {"tt_cyrl": " улы", "tt_latn": " uly"},
    "female": {"tt_cyrl": " кызы", "tt_latn": " kyzy"},
}

REPEATED_FORMATION_TOKENS = ("улы", "кызы", "ovich", "ovna", "uly", "kyzy")


@dataclass(frozen=True)
class FormationMatch:
    policy: str
    classification: str
    base_tt_cyrl: str
    details: str


def _squash_spaces(value: str) -> str:
    return " ".join(value.split())


def has_suspicious_adjacent_repetition(value: str) -> bool:
    tokens = [token.casefold() for token in value.split() if token]
    return any(left == right for left, right in zip(tokens, tokens[1:]))


def has_repeated_formation_suffix(value: str) -> bool:
    folded = _squash_spaces(value).casefold()
    return any(f"{token} {token}" in folded for token in REPEATED_FORMATION_TOKENS)


def is_suspicious_repetition(value: str) -> bool:
    return has_suspicious_adjacent_repetition(value) or has_repeated_formation_suffix(value)


def detect_generated_formation(
    row: Mapping[str, str],
    *,
    tt_key: str = "canonical_tt_cyrl",
    ru_key: str = "canonical_ru_cyrl",
    tt_latn_key: str = "canonical_tt_latn",
    ru_latn_key: str = "canonical_ru_latn",
    gender_key: str = "gender",
) -> FormationMatch | None:
    tt_cyrl = row.get(tt_key, "")
    ru_cyrl = row.get(ru_key, "")
    tt_latn = row.get(tt_latn_key, "")
    ru_latn = row.get(ru_latn_key, "")
    gender = row.get(gender_key, "")
    suffixes = PATRONYMIC_SUFFIXES.get(gender)
    if suffixes is None:
        return None

    normalized_tt = _squash_spaces(tt_cyrl)
    normalized_tt_latn = _squash_spaces(tt_latn)
    if not (
        normalized_tt.endswith(suffixes["tt_cyrl"]) or normalized_tt_latn.endswith(suffixes["tt_latn"])
    ):
        return None

    malformed_reasons: list[str] = []
    if normalized_tt != tt_cyrl:
        malformed_reasons.append("irregular whitespace")
    if is_suspicious_repetition(normalized_tt) or is_suspicious_repetition(normalized_tt_latn):
        malformed_reasons.append("repeated formation tokens")
    if "Кызы" in tt_cyrl or "Улы" in tt_cyrl:
        malformed_reasons.append("unexpected casing in Tatar suffix")

    base_tt = normalized_tt.removesuffix(suffixes["tt_cyrl"]).strip()
    base_tt_latn = normalized_tt_latn.removesuffix(suffixes["tt_latn"]).strip()
    if not base_tt:
        malformed_reasons.append("missing Tatar base")
    if normalized_tt.endswith(suffixes["tt_cyrl"]) and not ru_cyrl:
        malformed_reasons.append("missing Russian patronymic")
    if normalized_tt_latn.endswith(suffixes["tt_latn"]) and not ru_latn:
        malformed_reasons.append("missing Latin patronymic")

    classification = "malformed_generated" if malformed_reasons else "valid_generated"
    details = ", ".join(malformed_reasons) if malformed_reasons else f"base={base_tt or base_tt_latn}"
    return FormationMatch(
        policy="patronymic",
        classification=classification,
        base_tt_cyrl=base_tt or base_tt_latn,
        details=details,
    )


def generate_patronymic(base: Mapping[str, str], gender: str) -> dict[str, str]:
    suffixes = PATRONYMIC_SUFFIXES.get(gender)
    if suffixes is None:
        raise ValueError(f"Unsupported patronymic gender: {gender}")
    tt_cyrl = base["canonical_tt_cyrl"].strip()
    ru_cyrl = base["canonical_ru_cyrl"].strip()
    tt_latn = base["canonical_tt_latn"].strip()
    ru_latn = base["canonical_ru_latn"].strip()
    ru_cyrl_base = ru_cyrl[:-1] if ru_cyrl.endswith(("й", "ь")) else ru_cyrl
    if ru_cyrl.endswith(("й", "ь", "и", "я", "е", "ё")):
        ru_suffix_cyrl = "евич" if gender == "male" else "евна"
        ru_suffix_latn = "evich" if gender == "male" else "evna"
    else:
        ru_suffix_cyrl = "ович" if gender == "male" else "овна"
        ru_suffix_latn = "ovich" if gender == "male" else "ovna"
    return {
        "canonical_tt_cyrl": f"{tt_cyrl}{suffixes['tt_cyrl']}",
        "canonical_ru_cyrl": f"{ru_cyrl_base}{ru_suffix_cyrl}",
        "canonical_tt_latn": f"{tt_latn}{suffixes['tt_latn']}",
        "canonical_ru_latn": f"{ru_latn}{ru_suffix_latn}",
    }

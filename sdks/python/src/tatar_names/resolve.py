from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from . import normalize
from .data import release_path


@dataclass(frozen=True)
class Form:
    name_id: str
    form: str
    profile: str
    confidence: float


def _forms_by_key(data_dir: str | Path | None = None) -> dict[str, list[Form]]:
    path = release_path("forms.csv", data_dir)
    forms: dict[str, list[Form]] = {}
    if not path.exists():
        return _aliases_by_key(data_dir)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = normalize.safe(row["form"])
            forms.setdefault(key, []).append(
                Form(
                    name_id=row["name_id"],
                    form=row["form"],
                    profile=row["profile"],
                    confidence=float(row["confidence"]),
                )
            )
    return forms


def _aliases_by_key(data_dir: str | Path | None = None) -> dict[str, list[Form]]:
    path = release_path("aliases.csv", data_dir)
    aliases: dict[str, list[Form]] = {}
    if not path.exists():
        return aliases
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = normalize.safe(row["alias"])
            aliases.setdefault(key, []).append(
                Form(
                    name_id=row["name_id"],
                    form=row["alias"],
                    profile=row["method"],
                    confidence=float(row["confidence"]),
                )
            )
    return aliases


def _names_by_id(data_dir: str | Path | None = None) -> dict[str, dict[str, str]]:
    path = release_path("names.csv", data_dir)
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["name_id"]: row for row in csv.DictReader(handle)}


def resolve(value: str, data_dir: str | Path | None = None) -> dict[str, object]:
    key = normalize.safe(value)
    forms = sorted(_forms_by_key(data_dir).get(key, []), key=lambda row: row.confidence, reverse=True)
    names = _names_by_id(data_dir)

    best = forms[0] if forms else None
    best_match = None
    if best:
        name = names.get(best.name_id, {})
        best_match = {
            "name_id": best.name_id,
            "canonical_ru": name.get("canonical_ru_cyrl", best.form),
            "canonical_tt": name.get("canonical_tt_cyrl", ""),
            "confidence": best.confidence,
            "matched_form": best.form,
            "method": best.profile,
        }

    candidates = []
    for form in forms:
        name = names.get(form.name_id, {})
        candidates.append(
            {
                "name_id": form.name_id,
                "canonical_ru": name.get("canonical_ru_cyrl", form.form),
                "canonical_tt": name.get("canonical_tt_cyrl", ""),
                "confidence": form.confidence,
                "matched_form": form.form,
                "method": form.profile,
            }
        )

    return {
        "input": value,
        "best_match": best_match,
        "candidates": candidates,
        "near_misses": [],
    }

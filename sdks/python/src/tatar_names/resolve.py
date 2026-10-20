from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from . import normalize
from .data import default_release_dir, release_path


@dataclass(frozen=True)
class Form:
    form_id: str
    name_id: str
    form: str
    form_role: str
    profile: str
    confidence: float
    merge_policy: str


def _forms_by_key(data_dir: str | Path | None = None) -> dict[str, list[Form]]:
    path = release_path("forms.csv", data_dir)
    forms: dict[str, list[Form]] = {}
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = normalize.safe(row["form"])
            forms.setdefault(key, []).append(
                Form(
                    form_id=row["form_id"],
                    name_id=row["name_id"],
                    form=row["form"],
                    form_role=row["form_role"],
                    profile=row["profile"],
                    confidence=float(row["confidence"]),
                    merge_policy=row["merge_policy"],
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
                    form_id=row["form_id"],
                    name_id=row["name_id"],
                    form=row["alias"],
                    form_role=row["alias_type"],
                    profile=row["method"],
                    confidence=float(row["confidence"]),
                    merge_policy=row["merge_policy"],
                )
            )
    return aliases


def _identities_by_id(data_dir: str | Path | None = None) -> dict[str, dict[str, str]]:
    path = release_path("identities.csv", data_dir)
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["name_id"]: row for row in csv.DictReader(handle)}


def _relations_by_name(data_dir: str | Path | None = None) -> dict[str, list[dict[str, str]]]:
    path = release_path("relations.csv", data_dir)
    relations: dict[str, list[dict[str, str]]] = {}
    if not path.exists():
        return relations
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            for kind_key, id_key in (("left_kind", "left_id"), ("right_kind", "right_id")):
                if row[kind_key] == "name":
                    relations.setdefault(row[id_key], []).append(row)
    return relations


@dataclass(frozen=True)
class ResolverSnapshot:
    """Immutable, fully-materialized lookup structures for one release dir."""

    forms_by_key: Mapping[str, tuple[Form, ...]]
    alias_forms_by_key: Mapping[str, tuple[Form, ...]]
    identities_by_id: Mapping[str, Mapping[str, str]]
    relations_by_name: Mapping[str, tuple[Mapping[str, str], ...]]


def _release_dir(data_dir: str | Path | None) -> Path:
    return Path(data_dir) if data_dir is not None else default_release_dir()


# Keyed by the resolved release directory path, not table content: edits to
# the CSVs under an already-seen path stay invisible until clear_resolver_cache().
@lru_cache(maxsize=None)
def _snapshot_for(release_dir: Path) -> ResolverSnapshot:
    return ResolverSnapshot(
        forms_by_key=MappingProxyType({key: tuple(rows) for key, rows in _forms_by_key(release_dir).items()}),
        alias_forms_by_key=MappingProxyType({key: tuple(rows) for key, rows in _aliases_by_key(release_dir).items()}),
        identities_by_id=MappingProxyType(dict(_identities_by_id(release_dir))),
        relations_by_name=MappingProxyType(
            {key: tuple(rows) for key, rows in _relations_by_name(release_dir).items()}
        ),
    )


def clear_resolver_cache() -> None:
    """Drop all cached snapshots so subsequent resolve() calls re-read the tables."""
    _snapshot_for.cache_clear()


def _match_type(form: Form) -> str:
    if form.form_role in {"official_tt", "official_ru_or_russified_primary"}:
        return "official_form"
    if form.form_role in {"tt_latin_transliteration", "passport_latin"}:
        return "script_variant"
    if form.merge_policy == "candidate_only":
        return "candidate_only"
    return "variant"


MERGE_ADVISORY = (
    "merge_recommendation describes form-level linkage only; "
    "person-record merges require independent evidence"
)


def _score(form: Form) -> tuple[float, int]:
    # Every candidate form shares the query's normalized key by construction,
    # so the former exact_bonus was equal across all candidates and dropping
    # it leaves the (confidence, merge_bonus) ordering unchanged.
    merge_bonus = 1 if form.merge_policy == "auto_merge" else 0
    return (form.confidence, merge_bonus)


def resolve(value: str, data_dir: str | Path | None = None) -> dict[str, object]:
    key = normalize.safe(value)
    snapshot = _snapshot_for(_release_dir(data_dir))

    matched_forms = list(snapshot.forms_by_key.get(key, ()))
    if not matched_forms:
        matched_forms = list(snapshot.alias_forms_by_key.get(key, ()))

    by_name: dict[str, Form] = {}
    for form in matched_forms:
        best = by_name.get(form.name_id)
        if best is None or _score(form) > _score(best):
            by_name[form.name_id] = form

    ordered_forms = sorted(by_name.values(), key=_score, reverse=True)

    candidates: list[dict[str, object]] = []
    for form in ordered_forms:
        name = snapshot.identities_by_id.get(form.name_id, {})
        candidates.append(
            {
                "name_id": form.name_id,
                "matched_form": form.form,
                "matched_form_id": form.form_id,
                "canonical_ru": name.get("canonical_ru_cyrl", form.form),
                "canonical_tt": name.get("canonical_tt_cyrl", ""),
                "confidence": form.confidence,
                "match_type": _match_type(form),
                "merge_policy": form.merge_policy,
            }
        )

    best_match = candidates[0] if candidates else None
    near_misses: list[dict[str, object]] = []
    relation_warnings: list[dict[str, object]] = []
    if best_match:
        for relation in snapshot.relations_by_name.get(best_match["name_id"], ()):
            if relation["relation"] != "near_confusable_but_distinct":
                continue
            other_name_id = relation["right_id"] if relation["left_id"] == best_match["name_id"] else relation["left_id"]
            other_name = snapshot.identities_by_id.get(other_name_id, {})
            warning = {
                "relation": relation["relation"],
                "other_name_id": other_name_id,
                "other_canonical_ru": other_name.get("canonical_ru_cyrl", ""),
                "other_canonical_tt": other_name.get("canonical_tt_cyrl", ""),
                "merge_policy": relation["merge_policy"],
                "confidence": float(relation["confidence"]),
                "reason": relation["notes"],
            }
            relation_warnings.append(warning)
            near_misses.append(
                {
                    "name_id": other_name_id,
                    "canonical_ru": other_name.get("canonical_ru_cyrl", ""),
                    "canonical_tt": other_name.get("canonical_tt_cyrl", ""),
                    "relation": relation["relation"],
                    "confidence": float(relation["confidence"]),
                }
            )

    merge_recommendation = "no_match"
    if best_match:
        if best_match["merge_policy"] == "auto_merge" and not relation_warnings:
            # A lexical form match cannot authorize merging person records,
            # so the value names what it knows: a form-level match.
            merge_recommendation = "form_match_auto_merge"
        elif best_match["merge_policy"] == "never_merge":
            merge_recommendation = "never_merge"
        else:
            merge_recommendation = "review_required"

    return {
        "input": value,
        "best_match": best_match,
        "candidates": candidates,
        "near_misses": near_misses,
        "relation_warnings": relation_warnings,
        "merge_recommendation": merge_recommendation,
        "advisory": MERGE_ADVISORY,
    }

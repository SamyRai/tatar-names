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
    script: str = ""
    language_tag: str = ""
    identity_status: str = ""
    source_id: str = ""


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
                    script=row["script"],
                    language_tag=row["language_tag"],
                    identity_status=row["identity_status"],
                    source_id=row["source_id"],
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
                    script=row["script"],
                    language_tag=row["language_tag"],
                    source_id=row["source_id"],
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
            # TN-17/ADR-009: mechanically derived same-identity edges remain in
            # the relations.csv view for consumers, but the internal lookup
            # index carries only independently evidenced relations.
            if row["evidence_type"] == "derived_identity_graph":
                continue
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
    _default_resolver.cache_clear()


def _match_type(form: Form) -> str:
    if form.identity_status == "ambiguous_candidate":
        # TN-15: the spelling itself is shared across identities; surfacing
        # that outranks the role the form plays for any single one of them.
        return "ambiguous_candidate"
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

LOOKUP_NOT_FOUND = "not_found"
LOOKUP_UNIQUE_CANDIDATE = "unique_candidate"
LOOKUP_AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class Candidate:
    """One lexical identity that a queried spelling could denote (TN-22)."""

    name_id: str
    matched_form: str
    matched_form_id: str
    script: str
    language_tag: str
    entity_type: str
    canonical_ru: str
    canonical_tt: str
    confidence: float
    match_type: str
    merge_policy: str
    identity_status: str
    source_id: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class LookupResult:
    """Outcome of one lookup: never an arbitrarily ranked single answer (ADR-005)."""

    query: str
    status: str
    candidates: tuple[Candidate, ...]
    near_misses: tuple[Mapping[str, object], ...]
    relation_warnings: tuple[Mapping[str, object], ...]
    merge_recommendation: str
    advisory: str


def _order_key(candidate: Candidate) -> tuple[float, int]:
    # Every candidate form shares the query's normalized key by construction,
    # so the former exact_bonus was equal across all candidates and dropping
    # it leaves the (confidence, merge_bonus) ordering unchanged.
    merge_bonus = 1 if candidate.merge_policy == "auto_merge" else 0
    return (candidate.confidence, merge_bonus)


class Resolver:
    """Read-only lexical lookup over one immutable release snapshot.

    lookup() reports not_found / unique_candidate / ambiguous and never
    resolves ambiguity through ranking (ADR-005): every matching identity is
    returned as a candidate with its own evidence references.
    """

    def __init__(self, snapshot: ResolverSnapshot) -> None:
        self._snapshot = snapshot

    @classmethod
    def from_path(cls, data_dir: str | Path | None = None) -> "Resolver":
        return cls(_snapshot_for(_release_dir(data_dir)))

    @classmethod
    def from_package(cls) -> "Resolver":
        # The corpus stays a release asset, so the packaged location is the
        # default release dir that from_path(None) resolves.
        return cls.from_path(None)

    def lookup(
        self,
        value: str,
        entity_type: str | None = None,
        language_hint: str | None = None,
        mode: str = "lookup",
    ) -> LookupResult:
        if mode not in {"lookup", "canonical"}:
            raise ValueError(f"unsupported lookup mode {mode!r}")
        key = normalize.safe(value)

        matched = list(self._snapshot.forms_by_key.get(key, ()))
        if not matched:
            matched = list(self._snapshot.alias_forms_by_key.get(key, ()))

        candidates = [self._candidate(form) for form in matched]
        if mode == "canonical":
            # The index itself is normalized, so canonical mode keeps the
            # normalized fetch and then requires the query to equal the
            # attested spelling verbatim.
            candidates = [c for c in candidates if c.matched_form == value]
        if entity_type is not None:
            candidates = [c for c in candidates if c.entity_type == entity_type]
        if language_hint is not None:
            # A hint narrows the candidate set; it never picks one winner
            # among the identities that remain (ADR-005).
            hinted = language_hint.strip().lower()
            candidates = [
                c
                for c in candidates
                if hinted in {c.language_tag.lower(), c.language_tag.split("-")[0].lower(), c.script.lower()}
            ]

        by_name: dict[str, Candidate] = {}
        for candidate in candidates:
            best = by_name.get(candidate.name_id)
            if best is None or _order_key(candidate) > _order_key(best):
                by_name[candidate.name_id] = candidate
        ordered = tuple(sorted(by_name.values(), key=_order_key, reverse=True))

        if not ordered:
            status = LOOKUP_NOT_FOUND
        elif len(ordered) == 1:
            status = LOOKUP_UNIQUE_CANDIDATE
        else:
            status = LOOKUP_AMBIGUOUS

        near_misses: list[dict[str, object]] = []
        relation_warnings: list[dict[str, object]] = []
        if ordered:
            for relation in self._snapshot.relations_by_name.get(ordered[0].name_id, ()):
                if relation["relation"] != "near_confusable_but_distinct":
                    continue
                other_name_id = (
                    relation["right_id"] if relation["left_id"] == ordered[0].name_id else relation["left_id"]
                )
                other_name = self._snapshot.identities_by_id.get(other_name_id, {})
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
        if ordered:
            top = ordered[0]
            if status == LOOKUP_AMBIGUOUS:
                # A shared spelling cannot authorize a merge on any candidate.
                merge_recommendation = "review_required"
            elif top.merge_policy == "auto_merge" and not relation_warnings:
                # A lexical form match cannot authorize merging person records,
                # so the value names what it knows: a form-level match.
                merge_recommendation = "form_match_auto_merge"
            elif top.merge_policy == "never_merge":
                merge_recommendation = "never_merge"
            else:
                merge_recommendation = "review_required"

        return LookupResult(
            query=value,
            status=status,
            candidates=ordered,
            near_misses=tuple(near_misses),
            relation_warnings=tuple(relation_warnings),
            merge_recommendation=merge_recommendation,
            advisory=MERGE_ADVISORY,
        )

    def _candidate(self, form: Form) -> Candidate:
        name = self._snapshot.identities_by_id.get(form.name_id, {})
        warnings = tuple(
            sorted({
                relation["relation"]
                for relation in self._snapshot.relations_by_name.get(form.name_id, ())
                if relation["relation"] == "near_confusable_but_distinct"
            })
        )
        return Candidate(
            name_id=form.name_id,
            matched_form=form.form,
            matched_form_id=form.form_id,
            script=form.script,
            language_tag=form.language_tag,
            entity_type=name.get("entity_type", ""),
            canonical_ru=name.get("canonical_ru_cyrl", form.form),
            canonical_tt=name.get("canonical_tt_cyrl", ""),
            confidence=form.confidence,
            match_type=_match_type(form),
            merge_policy=form.merge_policy,
            identity_status=form.identity_status,
            source_id=form.source_id,
            warnings=warnings,
        )


@lru_cache(maxsize=None)
def _default_resolver(release_dir: Path) -> Resolver:
    return Resolver.from_path(release_dir)


def _compat_candidate(candidate: Candidate) -> dict[str, object]:
    return {
        "name_id": candidate.name_id,
        "matched_form": candidate.matched_form,
        "matched_form_id": candidate.matched_form_id,
        "canonical_ru": candidate.canonical_ru,
        "canonical_tt": candidate.canonical_tt,
        "confidence": candidate.confidence,
        "match_type": candidate.match_type,
        "merge_policy": candidate.merge_policy,
    }


def resolve(value: str, data_dir: str | Path | None = None) -> dict[str, object]:
    """Backward-compatible adapter over :class:`Resolver`.lookup.

    Returns the pre-TN-22 result mapping unchanged; new code should call
    ``Resolver.lookup`` for the explicit status/candidate contract.
    """
    result = _default_resolver(_release_dir(data_dir)).lookup(value)
    return {
        "input": value,
        "best_match": _compat_candidate(result.candidates[0]) if result.candidates else None,
        "candidates": [_compat_candidate(c) for c in result.candidates],
        "near_misses": [dict(m) for m in result.near_misses],
        "relation_warnings": [dict(w) for w in result.relation_warnings],
        "merge_recommendation": result.merge_recommendation,
        "advisory": result.advisory,
    }

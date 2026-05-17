from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from .data import default_release_dir, default_source_dir, project_root
from .formations import detect_generated_formation, is_suspicious_repetition
from . import normalize
from .pipeline import release_table, source_table


def _parse_confusables() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in (project_root() / "rules" / "confusables.yaml").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("version:") or line == "do_not_merge:":
            continue
        if line.startswith("- "):
            if current:
                rows.append(current)
            current = {}
            payload = line[2:]
            if ":" in payload:
                key, value = payload.split(":", 1)
                current[key.strip()] = value.strip().strip('"')
            continue
        if current is not None and ":" in line:
            key, value = line.split(":", 1)
            current[key.strip()] = value.strip().strip('"')
    if current:
        rows.append(current)
    return rows


def analyze_patterns(
    source_dir: str | Path | None = None,
    release_dir: str | Path | None = None,
    sample_limit: int = 10,
) -> dict[str, object]:
    source_base = Path(source_dir) if source_dir is not None else default_source_dir()
    release_base = Path(release_dir) if release_dir is not None else default_release_dir()

    entities = source_table(source_base, "entities")
    attestations = source_table(source_base, "attestations")
    excluded = source_table(source_base, "excluded_entities")
    identities = release_table(release_base, "identities")
    forms = release_table(release_base, "forms")
    relations = release_table(release_base, "relations")
    review_queue = release_table(release_base, "review_queue")
    aliases = release_table(release_base, "aliases")
    identity_by_id = {row["name_id"]: row for row in identities}

    generated_exclusions = [row for row in excluded if row["reason"] == "generated_patronymic"]
    malformed_exclusions = [row for row in excluded if is_suspicious_repetition(row["canonical_tt_cyrl"])]
    missing_tt_exclusions = [row for row in excluded if row["reason"] == "missing_tatar_canonical"]

    stored_generated = [row for row in entities if detect_generated_formation(row)]
    suspicious_entities = [
        row
        for row in entities
        if any(
            is_suspicious_repetition(row[field])
            for field in ("canonical_tt_cyrl", "canonical_ru_cyrl", "canonical_tt_latn", "canonical_ru_latn")
        )
    ]
    entity_type_by_id = {row["entity_id"]: row["entity_type"] for row in entities}
    source_alias_types: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    source_alias_entities: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in attestations:
        if row["is_canonical"] == "true":
            continue
        key = (normalize.safe(row["form"]), row["script"], row["language_tag"])
        source_alias_types[key].add(entity_type_by_id[row["entity_id"]])
        source_alias_entities[key].add(row["entity_id"])
    cross_type_source_aliases = [
        {"normalized_form": form, "script": script, "language_tag": language_tag, "entity_ids": sorted(source_alias_entities[(form, script, language_tag)])}
        for (form, script, language_tag), types in source_alias_types.items()
        if len(types) > 1
    ]

    exact_form_to_names: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in forms:
        exact_form_to_names[(row["form"], row["script"], row["language_tag"])].add(row["name_id"])
    collisions = [
        {"form": form, "script": script, "language_tag": language_tag, "name_ids": sorted(name_ids)}
        for (form, script, language_tag), name_ids in exact_form_to_names.items()
        if len(name_ids) > 1
    ]

    alias_redundancy = []
    alias_method_counts: Counter[str] = Counter()
    for row in aliases:
        name = identity_by_id[row["name_id"]]
        alias_method_counts[row["method"]] += 1
        canonical_values = {
            name["canonical_tt_cyrl"],
            name["canonical_ru_cyrl"],
            name["canonical_tt_latn"],
            name["canonical_ru_latn"],
        }
        if row["alias"] in canonical_values:
            alias_redundancy.append(row)

    relation_counts = Counter(row["relation"] for row in relations)
    review_counts = Counter(row["queue_reason"] for row in review_queue)
    names_without_relations = sorted(
        row["name_id"]
        for row in identities
        if not any(
            relation["left_kind"] == "name"
            and relation["left_id"] == row["name_id"]
            or relation["right_kind"] == "name"
            and relation["right_id"] == row["name_id"]
            for relation in relations
        )
    )
    names_missing_primary = sorted(
        row["name_id"]
        for row in identities
        if not row["primary_form_global"] or not row["primary_form_tt"] or not row["primary_form_ru"]
    )

    known_confusable_pairs = {
        tuple(sorted((row["left_id"], row["right_id"])))
        for row in relations
        if row["relation"] == "near_confusable_but_distinct" and row["left_kind"] == row["right_kind"] == "name"
    }
    canonical_index: dict[str, set[str]] = defaultdict(set)
    for row in identities:
        for value in (row["canonical_tt_cyrl"], row["canonical_ru_cyrl"], row["canonical_tt_latn"], row["canonical_ru_latn"]):
            canonical_index[normalize.safe(value)].add(row["name_id"])
    missing_confusable_rules = []
    for pair in _parse_confusables():
        left = canonical_index.get(normalize.safe(pair.get("left", "")), set())
        right = canonical_index.get(normalize.safe(pair.get("right", "")), set())
        if not left or not right:
            missing_confusable_rules.append(pair)
            continue
        if not any(tuple(sorted((l, r))) in known_confusable_pairs for l in left for r in right if l != r):
            missing_confusable_rules.append(pair)

    return {
        "totals": {
            "source_entities": len(entities),
            "source_attestations": len(attestations),
            "excluded_entities": len(excluded),
            "release_identities": len(identities),
            "release_forms": len(forms),
            "release_relations": len(relations),
            "release_review_queue": len(review_queue),
            "release_aliases": len(aliases),
        },
        "generated_formations": {
            "stored_in_entities": len(stored_generated),
            "excluded_patronymics": len(generated_exclusions),
            "examples_excluded": generated_exclusions[:sample_limit],
        },
        "source_quality": {
            "missing_tatar_canonical_excluded": len(missing_tt_exclusions),
            "suspicious_repetition_in_entities": len(suspicious_entities),
            "suspicious_repetition_excluded": len(malformed_exclusions),
            "cross_type_source_alias_candidates": len(cross_type_source_aliases),
            "examples_suspicious_entities": suspicious_entities[:sample_limit],
            "examples_missing_tatar": missing_tt_exclusions[:sample_limit],
            "examples_cross_type_source_alias_candidates": cross_type_source_aliases[:sample_limit],
        },
        "release_quality": {
            "exact_form_collisions": len(collisions),
            "examples_exact_form_collisions": collisions[:sample_limit],
            "alias_redundant_with_canonical": len(alias_redundancy),
            "alias_by_method": dict(alias_method_counts.most_common()),
            "relation_by_type": dict(relation_counts.most_common()),
            "review_by_reason": dict(review_counts.most_common()),
            "names_without_relation_coverage": len(names_without_relations),
            "identities_missing_primary_forms": len(names_missing_primary),
            "hard_negative_rules_missing_release_coverage": len(missing_confusable_rules),
            "examples_missing_confusable_rules": missing_confusable_rules[:sample_limit],
            "examples_redundant_aliases": alias_redundancy[:sample_limit],
        },
        "excluded_reasons": dict(Counter(row["reason"] for row in excluded).most_common()),
    }

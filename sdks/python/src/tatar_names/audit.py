from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from .data import default_release_dir, default_source_dir
from .formations import detect_generated_formation, is_suspicious_repetition
from .pipeline import release_table, source_table


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
    names = release_table(release_base, "names")
    forms = release_table(release_base, "forms")

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

    exact_form_to_names: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in forms:
        exact_form_to_names[(row["form"], row["script"], row["language_tag"])].add(row["name_id"])
    collisions = [
        {"form": form, "script": script, "language_tag": language_tag, "name_ids": sorted(name_ids)}
        for (form, script, language_tag), name_ids in exact_form_to_names.items()
        if len(name_ids) > 1
    ]

    return {
        "totals": {
            "source_entities": len(entities),
            "source_attestations": len(attestations),
            "excluded_entities": len(excluded),
            "release_names": len(names),
            "release_forms": len(forms),
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
            "examples_suspicious_entities": suspicious_entities[:sample_limit],
            "examples_missing_tatar": missing_tt_exclusions[:sample_limit],
        },
        "release_quality": {
            "exact_form_collisions": len(collisions),
            "examples_exact_form_collisions": collisions[:sample_limit],
        },
        "excluded_reasons": dict(Counter(row["reason"] for row in excluded).most_common()),
    }

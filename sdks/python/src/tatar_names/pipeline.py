from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from . import normalize
from .data import default_release_dir, default_source_dir, project_root
from .formations import detect_generated_formation, is_suspicious_repetition

BAD_START_RE = re.compile(r"^[^\wА-Яа-яӘәӨөҮүҖҗҢңҺһЁё]")
VALID_GENDERS = {"male", "female", "unisex", "unknown"}
VALID_ENTITY_TYPES = {"given", "surname"}
VALID_STATUSES = {"active", "deprecated", "disputed"}
VALID_SCRIPTS = {"Cyrl", "Latn"}
VALID_FORM_KINDS = {"canonical", "observed_variant", "transliterated", "normalized_source"}
VALID_FORM_PROFILES = {
    "ru_adaptation",
    "tt_original",
    "tt_cyrl_to_tt_latn_rt2013",
    "ru_cyrl_to_latn_mvd_doc",
    "common_variant",
}
VALID_FORM_ROLES = {
    "official_tt",
    "official_ru_or_russified_primary",
    "tt_latin_transliteration",
    "passport_latin",
    "common_observed",
}
VALID_IDENTITY_STATUSES = {"canonical", "variant", "alias"}
VALID_MERGE_POLICIES = {"auto_merge", "candidate_only", "never_merge", "review_required"}
VALID_RELATIONS = {
    "same_name_official_pair",
    "same_name_script_variant",
    "same_name_adapted_form",
    "same_etymon_but_distinct",
    "possible_variant",
    "near_confusable_but_distinct",
    "russified_primary_form",
    "tatarized_form_of_non_tatar_name",
    "review_candidate",
}
VALID_LINK_KINDS = {"name", "form"}
VALID_REVIEW_SUBJECT_KINDS = {"excluded_entity", "form", "relation", "rule"}
FORM_ROLE_BY_PROFILE = {
    "tt_original": "official_tt",
    "ru_adaptation": "official_ru_or_russified_primary",
    "tt_cyrl_to_tt_latn_rt2013": "tt_latin_transliteration",
    "ru_cyrl_to_latn_mvd_doc": "passport_latin",
    "common_variant": "common_observed",
}
IDENTITY_STATUS_BY_PROFILE = {
    "tt_original": "canonical",
    "ru_adaptation": "canonical",
    "tt_cyrl_to_tt_latn_rt2013": "variant",
    "ru_cyrl_to_latn_mvd_doc": "variant",
    "common_variant": "alias",
}
MERGE_POLICY_BY_PROFILE = {
    "tt_original": "auto_merge",
    "ru_adaptation": "auto_merge",
    "tt_cyrl_to_tt_latn_rt2013": "auto_merge",
    "ru_cyrl_to_latn_mvd_doc": "auto_merge",
    "common_variant": "candidate_only",
}
ALIAS_TYPE_BY_FORM_ROLE = {
    "official_tt": "official_tt",
    "official_ru_or_russified_primary": "official_ru",
    "tt_latin_transliteration": "transliteration",
    "passport_latin": "passport_latin",
    "common_observed": "common_variant",
}


def has_cyrillic(value: str) -> bool:
    return any("\u0400" <= char <= "\u04ff" for char in value)


def has_latin(value: str) -> bool:
    return any(("A" <= char <= "Z") or ("a" <= char <= "z") for char in value)


def read_csv_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv_table(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def bibliography_source_ids(base: Path) -> set[str]:
    bib_path = base.parent.parent / "bibliography.bib"
    if not bib_path.exists():
        bib_path = project_root() / "bibliography.bib"
    text = bib_path.read_text(encoding="utf-8")
    return set(re.findall(r"@\w+\{([^,]+),", text))


def source_table(base: Path, name: str) -> list[dict[str, str]]:
    return read_csv_table(base / f"{name}.csv")


def release_table(base: Path, name: str) -> list[dict[str, str]]:
    return read_csv_table(base / f"{name}.csv")


def _validate_name_like(value: str, *, allow_empty: bool = False) -> bool:
    if allow_empty and value == "":
        return True
    if not value.strip() or value != value.strip():
        return False
    if BAD_START_RE.search(value) or any(char.isdigit() for char in value):
        return False
    if has_cyrillic(value) and has_latin(value):
        return False
    return True


def _float_str(value: str) -> float:
    return float(value or "0")


def _parse_confusables(path: Path | None = None) -> list[dict[str, str]]:
    confusables_path = path if path is not None else project_root() / "rules" / "confusables.yaml"
    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in confusables_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("version:") or stripped == "do_not_merge:":
            continue
        if stripped.startswith("- "):
            if current:
                rows.append(current)
            current = {}
            payload = stripped[2:]
            if ":" in payload:
                key, value = payload.split(":", 1)
                current[key.strip()] = value.strip().strip('"')
            continue
        if current is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = value.strip().strip('"')
    if current:
        rows.append(current)
    return rows


def _form_quality_key(row: dict[str, str]) -> tuple[int, float, int]:
    canonical_score = 1 if row["is_canonical"] == "true" else 0
    profile_priority = {
        "tt_original": 5,
        "ru_adaptation": 4,
        "tt_cyrl_to_tt_latn_rt2013": 3,
        "ru_cyrl_to_latn_mvd_doc": 2,
        "common_variant": 1,
    }[row["profile"]]
    return (canonical_score, _float_str(row["confidence"]), profile_priority)


def _release_form_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "form_id": row["attestation_id"].replace("at_", "f_"),
        "name_id": row["entity_id"],
        "form": row["form"],
        "script": row["script"],
        "language_tag": row["language_tag"],
        "form_role": FORM_ROLE_BY_PROFILE[row["profile"]],
        "identity_status": IDENTITY_STATUS_BY_PROFILE[row["profile"]],
        "profile": row["profile"],
        "confidence": row["confidence"],
        "source_id": row["source_id"],
        "evidence_id": row["evidence_id"],
        "merge_policy": MERGE_POLICY_BY_PROFILE[row["profile"]],
    }


def _review_queue_row(
    review_id: str,
    subject_kind: str,
    subject_id: str,
    queue_reason: str,
    suggested_relation: str,
    source_id: str,
    evidence_id: str,
    notes: str,
) -> dict[str, str]:
    return {
        "review_id": review_id,
        "subject_kind": subject_kind,
        "subject_id": subject_id,
        "queue_reason": queue_reason,
        "suggested_relation": suggested_relation,
        "source_id": source_id,
        "evidence_id": evidence_id,
        "notes": notes,
    }


def _relation_kind_for_form(form_row: dict[str, str], identity: dict[str, str]) -> str:
    form_role = form_row["form_role"]
    if form_role == "official_tt":
        return "same_name_official_pair"
    if form_role == "official_ru_or_russified_primary":
        if form_row["form"] == identity["primary_form_ru"] and identity["primary_form_ru"] != identity["primary_form_tt"]:
            return "russified_primary_form"
        return "same_name_official_pair"
    if form_role in {"tt_latin_transliteration", "passport_latin"}:
        return "same_name_script_variant"
    return "review_candidate"


def validate_source(data_dir: str | Path | None = None) -> list[str]:
    base = Path(data_dir) if data_dir is not None else default_source_dir()
    errors: list[str] = []
    entities = source_table(base, "entities")
    attestations = source_table(base, "attestations")
    excluded = source_table(base, "excluded_entities")
    known_source_ids = bibliography_source_ids(base)

    entity_ids = {row["entity_id"] for row in entities}
    entity_by_id = {row["entity_id"]: row for row in entities}
    if len(entity_ids) != len(entities):
        errors.append("duplicate entity_id values in entities.csv")

    for row in entities:
        entity_id = row["entity_id"]
        if row["entity_type"] not in VALID_ENTITY_TYPES:
            errors.append(f"{entity_id} has invalid entity_type {row['entity_type']}")
        if row["gender"] not in VALID_GENDERS:
            errors.append(f"{entity_id} has invalid gender {row['gender']}")
        if row["status"] not in VALID_STATUSES:
            errors.append(f"{entity_id} has invalid status {row['status']}")
        if row["source_id"] not in known_source_ids:
            errors.append(f"{entity_id} has unknown source_id {row['source_id']}")
        for field in ("canonical_tt_cyrl", "canonical_ru_cyrl", "canonical_tt_latn", "canonical_ru_latn"):
            if not _validate_name_like(row[field]):
                errors.append(f"{entity_id} has malformed {field} {row[field]!r}")
            if is_suspicious_repetition(row[field]):
                errors.append(f"{entity_id} has suspicious repetition in {field} {row[field]!r}")
        formation = detect_generated_formation(row)
        if formation and row["is_lexical_exception"] != "true":
            errors.append(
                f"{entity_id} stores generated formation {formation.policy} ({formation.classification}): {row['canonical_tt_cyrl']!r}"
            )

    attestation_ids = {row["attestation_id"] for row in attestations}
    if len(attestation_ids) != len(attestations):
        errors.append("duplicate attestation_id values in attestations.csv")

    alias_candidate_types: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    alias_candidate_entities: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in attestations:
        attestation_id = row["attestation_id"]
        if row["entity_id"] not in entity_ids:
            errors.append(f"attestation {attestation_id} references unknown entity_id {row['entity_id']}")
        if row["script"] not in VALID_SCRIPTS:
            errors.append(f"attestation {attestation_id} has invalid script {row['script']}")
        if row["form_kind"] not in VALID_FORM_KINDS:
            errors.append(f"attestation {attestation_id} has invalid form_kind {row['form_kind']}")
        if row["profile"] not in VALID_FORM_PROFILES:
            errors.append(f"attestation {attestation_id} has invalid profile {row['profile']}")
        if row["source_id"] not in known_source_ids:
            errors.append(f"attestation {attestation_id} has unknown source_id {row['source_id']}")
        if row["is_canonical"] not in {"true", "false"}:
            errors.append(f"attestation {attestation_id} has invalid is_canonical {row['is_canonical']}")
        if not _validate_name_like(row["form"]):
            errors.append(f"attestation {attestation_id} has malformed form {row['form']!r}")
        if is_suspicious_repetition(row["form"]):
            errors.append(f"attestation {attestation_id} has suspicious repetition in form {row['form']!r}")
        formation = detect_generated_formation(
            {
                "canonical_tt_cyrl": row["form"] if row["language_tag"] == "tt-Cyrl" else "",
                "canonical_ru_cyrl": row["form"] if row["language_tag"] == "ru-Cyrl" else "",
                "canonical_tt_latn": row["form"] if row["language_tag"] == "tt-Latn" else "",
                "canonical_ru_latn": row["form"] if row["language_tag"] == "ru-Latn" else "",
                "gender": entity_by_id.get(row["entity_id"], {}).get("gender", "unknown"),
            }
        )
        if formation:
            errors.append(f"attestation {attestation_id} stores generated formation {formation.policy}: {row['form']!r}")
        if row["is_canonical"] == "false":
            key = (normalize.safe(row["form"]), row["script"], row["language_tag"])
            alias_candidate_types[key].add(entity_by_id[row["entity_id"]]["entity_type"])
            alias_candidate_entities[key].add(row["entity_id"])

    for key, types in alias_candidate_types.items():
        if len(types) > 1:
            errors.append(
                f"normalized alias candidate {key!r} spans multiple entity types: {', '.join(sorted(alias_candidate_entities[key]))}"
            )

    for row in excluded:
        source_id = row["source_id"]
        if source_id and source_id not in known_source_ids:
            errors.append(f"excluded entity {row['original_name_id']} has unknown source_id {source_id}")

    return errors


def build_release_rows(source_dir: str | Path | None = None) -> dict[str, list[dict[str, str]]]:
    base = Path(source_dir) if source_dir is not None else default_source_dir()
    entities = source_table(base, "entities")
    attestations = source_table(base, "attestations")
    excluded = source_table(base, "excluded_entities")

    active_entities = [row for row in entities if row["status"] == "active"]
    entity_ids = {row["entity_id"] for row in active_entities}
    entity_by_id = {row["entity_id"]: row for row in active_entities}

    identities_rows = [
        {
            "name_id": row["entity_id"],
            "entity_type": row["entity_type"],
            "gender": row["gender"],
            "origin_family": "unknown",
            "usage_community": "tatar_registry",
            "canonical_tt_cyrl": row["canonical_tt_cyrl"],
            "canonical_ru_cyrl": row["canonical_ru_cyrl"],
            "canonical_tt_latn": row["canonical_tt_latn"],
            "canonical_ru_latn": row["canonical_ru_latn"],
            "primary_form_global": row["canonical_ru_cyrl"],
            "primary_form_tt": row["canonical_tt_cyrl"],
            "primary_form_ru": row["canonical_ru_cyrl"],
            "source_id": row["source_id"],
            "source_row": row["source_row"],
            "status": row["status"],
            "notes": row["notes"],
        }
        for row in active_entities
    ]
    identities_rows.sort(key=lambda row: row["name_id"])

    candidate_forms = [row for row in attestations if row["entity_id"] in entity_ids]
    exact_to_rows: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in candidate_forms:
        exact_to_rows[(row["form"], row["script"], row["language_tag"])].append(row)

    forms_rows: list[dict[str, str]] = []
    for rows in exact_to_rows.values():
        if len({row["entity_id"] for row in rows}) > 1:
            continue
        best = max(rows, key=_form_quality_key)
        forms_rows.append(_release_form_row(best))
    forms_rows.sort(key=lambda row: row["form_id"])

    forms_by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in forms_rows:
        forms_by_name[row["name_id"]].append(row)

    relations_rows: list[dict[str, str]] = []
    relation_index = 1

    def add_relation(
        left_kind: str,
        left_id: str,
        right_kind: str,
        right_id: str,
        relation: str,
        merge_policy: str,
        confidence: str,
        evidence_type: str,
        source_id: str,
        evidence_id: str,
        notes: str,
    ) -> None:
        nonlocal relation_index
        relations_rows.append(
            {
                "relation_id": f"rel_{relation_index:07d}",
                "left_kind": left_kind,
                "left_id": left_id,
                "right_kind": right_kind,
                "right_id": right_id,
                "relation": relation,
                "merge_policy": merge_policy,
                "confidence": confidence,
                "evidence_type": evidence_type,
                "source_id": source_id,
                "evidence_id": evidence_id,
                "notes": notes,
            }
        )
        relation_index += 1

    review_rows: list[dict[str, str]] = []
    review_index = 1

    def add_review(
        subject_kind: str,
        subject_id: str,
        queue_reason: str,
        suggested_relation: str,
        source_id: str,
        evidence_id: str,
        notes: str,
    ) -> None:
        nonlocal review_index
        review_rows.append(
            _review_queue_row(
                f"rq_{review_index:07d}",
                subject_kind,
                subject_id,
                queue_reason,
                suggested_relation,
                source_id,
                evidence_id,
                notes,
            )
        )
        review_index += 1

    identity_by_id = {row["name_id"]: row for row in identities_rows}
    for form_row in forms_rows:
        identity = identity_by_id[form_row["name_id"]]
        relation = _relation_kind_for_form(form_row, identity)
        add_relation(
            "name",
            form_row["name_id"],
            "form",
            form_row["form_id"],
            relation,
            form_row["merge_policy"],
            form_row["confidence"],
            "source_attestation",
            form_row["source_id"],
            form_row["evidence_id"],
            form_row["form_role"],
        )
        if form_row["merge_policy"] in {"candidate_only", "review_required"}:
            add_review(
                "form",
                form_row["form_id"],
                "weak_evidence_form",
                "review_candidate",
                form_row["source_id"],
                form_row["evidence_id"],
                form_row["form"],
            )

    for name_id, name_forms in forms_by_name.items():
        auto_forms = [row for row in name_forms if row["merge_policy"] == "auto_merge"]
        for left, right in combinations(sorted(auto_forms, key=lambda row: row["form_id"]), 2):
            relation = "same_name_script_variant"
            if (
                {left["form_role"], right["form_role"]} == {"official_tt", "official_ru_or_russified_primary"}
                and left["script"] == right["script"] == "Cyrl"
            ):
                relation = "same_name_official_pair"
            elif left["script"] == right["script"] == "Cyrl" and left["form"] == right["form"]:
                relation = "same_name_adapted_form"
            add_relation(
                "form",
                left["form_id"],
                "form",
                right["form_id"],
                relation,
                "auto_merge",
                f"{min(_float_str(left['confidence']), _float_str(right['confidence'])):.2f}",
                "derived_identity_graph",
                entity_by_id[name_id]["source_id"],
                entity_by_id[name_id]["source_row"],
                name_id,
            )

    names_by_canonical: dict[str, set[str]] = defaultdict(set)
    for row in identities_rows:
        for canonical in (row["canonical_tt_cyrl"], row["canonical_ru_cyrl"], row["canonical_tt_latn"], row["canonical_ru_latn"]):
            names_by_canonical[normalize.safe(canonical)].add(row["name_id"])

    for pair in _parse_confusables():
        left_ids = names_by_canonical.get(normalize.safe(pair.get("left", "")), set())
        right_ids = names_by_canonical.get(normalize.safe(pair.get("right", "")), set())
        if not left_ids or not right_ids:
            add_review(
                "rule",
                f"{pair.get('left', '')}::{pair.get('right', '')}",
                "confusable_rule_not_in_dataset",
                "near_confusable_but_distinct",
                "confusables_rule",
                "",
                pair.get("reason", ""),
            )
            continue
        for left_id in sorted(left_ids):
            for right_id in sorted(right_ids):
                if left_id == right_id:
                    continue
                add_relation(
                    "name",
                    left_id,
                    "name",
                    right_id,
                    "near_confusable_but_distinct",
                    "never_merge",
                    "0.99",
                    "confusables_rule",
                    "confusables_rule",
                    "",
                    pair.get("reason", ""),
                )

    for row in excluded:
        add_review(
            "excluded_entity",
            row["original_name_id"],
            row["reason"],
            "review_candidate",
            row["source_id"],
            row["source_row"],
            row["notes"],
        )

    alias_candidates: list[dict[str, str]] = []
    for row in forms_rows:
        if row["identity_status"] == "canonical":
            continue
        identity = identity_by_id[row["name_id"]]
        canonical_values = {
            identity["canonical_tt_cyrl"],
            identity["canonical_ru_cyrl"],
            identity["canonical_tt_latn"],
            identity["canonical_ru_latn"],
        }
        if row["form"] in canonical_values:
            continue
        alias_candidates.append(
            {
                "form_id": row["form_id"],
                "name_id": row["name_id"],
                "alias": row["form"],
                "script": row["script"],
                "language_tag": row["language_tag"],
                "alias_type": ALIAS_TYPE_BY_FORM_ROLE[row["form_role"]],
                "method": row["profile"],
                "confidence": row["confidence"],
                "merge_policy": row["merge_policy"],
                "source_id": row["source_id"],
                "rule_id": row["profile"] if "latn" in row["profile"] else "",
            }
        )

    safe_alias_to_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in alias_candidates:
        safe_alias_to_rows[normalize.safe(row["alias"])].append(row)

    aliases_rows: list[dict[str, str]] = []
    for rows in safe_alias_to_rows.values():
        if len({row["name_id"] for row in rows}) > 1:
            continue
        aliases_rows.append(max(rows, key=lambda row: (_float_str(row["confidence"]), row["merge_policy"] == "auto_merge")))
    aliases_rows.sort(key=lambda row: (row["name_id"], row["alias"], row["method"]))
    for index, row in enumerate(aliases_rows, start=1):
        row["alias_id"] = f"a_{index:07d}"

    relations_rows.sort(key=lambda row: row["relation_id"])
    review_rows.sort(key=lambda row: row["review_id"])
    return {
        "identities": identities_rows,
        "forms": forms_rows,
        "relations": relations_rows,
        "review_queue": review_rows,
        "aliases": aliases_rows,
    }


def validate_release(data_dir: str | Path | None = None) -> list[str]:
    base = Path(data_dir) if data_dir is not None else default_release_dir()
    errors: list[str] = []
    identities = release_table(base, "identities")
    forms = release_table(base, "forms")
    relations = release_table(base, "relations")
    review_queue = release_table(base, "review_queue")
    aliases = release_table(base, "aliases")
    known_source_ids = bibliography_source_ids(base) | {"confusables_rule"}

    name_ids = {row["name_id"] for row in identities}
    identity_by_id = {row["name_id"]: row for row in identities}
    if len(name_ids) != len(identities):
        errors.append("duplicate name_id values in identities.csv")

    for row in identities:
        name_id = row["name_id"]
        if row["entity_type"] not in VALID_ENTITY_TYPES:
            errors.append(f"{name_id} has invalid entity_type {row['entity_type']}")
        if row["gender"] not in VALID_GENDERS:
            errors.append(f"{name_id} has invalid gender {row['gender']}")
        if row["status"] not in VALID_STATUSES:
            errors.append(f"{name_id} has invalid status {row['status']}")
        if not row["origin_family"]:
            errors.append(f"{name_id} has empty origin_family")
        if not row["usage_community"]:
            errors.append(f"{name_id} has empty usage_community")
        if row["source_id"] not in known_source_ids:
            errors.append(f"{name_id} has unknown source_id {row['source_id']}")
        for field in (
            "canonical_tt_cyrl",
            "canonical_ru_cyrl",
            "canonical_tt_latn",
            "canonical_ru_latn",
            "primary_form_global",
            "primary_form_tt",
            "primary_form_ru",
        ):
            if not _validate_name_like(row[field]):
                errors.append(f"{name_id} has malformed {field} {row[field]!r}")
        if detect_generated_formation(row):
            errors.append(f"{name_id} leaked generated formation into release: {row['canonical_tt_cyrl']!r}")

    form_ids = {row["form_id"] for row in forms}
    form_by_id = {row["form_id"]: row for row in forms}
    if len(form_ids) != len(forms):
        errors.append("duplicate form_id values in forms.csv")

    exact_form_to_names: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    name_to_auto_forms: dict[str, set[str]] = defaultdict(set)
    for row in forms:
        form = row["form"]
        name_id = row["name_id"]
        if name_id not in name_ids:
            errors.append(f"form {row['form_id']} references unknown name_id {name_id}")
        if row["script"] not in VALID_SCRIPTS:
            errors.append(f"form {row['form_id']} has invalid script {row['script']}")
        if row["form_role"] not in VALID_FORM_ROLES:
            errors.append(f"form {row['form_id']} has invalid form_role {row['form_role']}")
        if row["identity_status"] not in VALID_IDENTITY_STATUSES:
            errors.append(f"form {row['form_id']} has invalid identity_status {row['identity_status']}")
        if row["profile"] not in VALID_FORM_PROFILES:
            errors.append(f"form {row['form_id']} has invalid profile {row['profile']}")
        if row["merge_policy"] not in VALID_MERGE_POLICIES:
            errors.append(f"form {row['form_id']} has invalid merge_policy {row['merge_policy']}")
        if row["source_id"] not in known_source_ids:
            errors.append(f"form {row['form_id']} has unknown source_id {row['source_id']}")
        if not _validate_name_like(form):
            errors.append(f"form {row['form_id']} has malformed form {form!r}")
        if detect_generated_formation(
            {
                "canonical_tt_cyrl": form if row["language_tag"] == "tt-Cyrl" else "",
                "canonical_ru_cyrl": form if row["language_tag"] == "ru-Cyrl" else "",
                "canonical_tt_latn": form if row["language_tag"] == "tt-Latn" else "",
                "canonical_ru_latn": form if row["language_tag"] == "ru-Latn" else "",
                "gender": identity_by_id.get(name_id, {}).get("gender", "unknown"),
            }
        ):
            errors.append(f"form {row['form_id']} leaked generated formation into release: {form!r}")
        exact_form_to_names[(row["form"], row["script"], row["language_tag"])].add(name_id)
        if row["merge_policy"] == "auto_merge":
            name_to_auto_forms[name_id].add(row["form_id"])

    for key, ids in exact_form_to_names.items():
        if len(ids) > 1:
            errors.append(f"exact release form {key!r} maps to multiple names: {', '.join(sorted(ids))}")

    missing_auto_forms = [name_id for name_id in sorted(name_ids) if not name_to_auto_forms.get(name_id)]
    if missing_auto_forms:
        errors.append(f"names without auto-merge forms: {', '.join(missing_auto_forms[:10])}")

    relation_ids = {row["relation_id"] for row in relations}
    if len(relation_ids) != len(relations):
        errors.append("duplicate relation_id values in relations.csv")

    name_to_relation_count: dict[str, int] = defaultdict(int)
    for row in relations:
        relation_id = row["relation_id"]
        if row["left_kind"] not in VALID_LINK_KINDS:
            errors.append(f"relation {relation_id} has invalid left_kind {row['left_kind']}")
        if row["right_kind"] not in VALID_LINK_KINDS:
            errors.append(f"relation {relation_id} has invalid right_kind {row['right_kind']}")
        if row["relation"] not in VALID_RELATIONS:
            errors.append(f"relation {relation_id} has invalid relation {row['relation']}")
        if row["merge_policy"] not in VALID_MERGE_POLICIES:
            errors.append(f"relation {relation_id} has invalid merge_policy {row['merge_policy']}")
        if row["source_id"] not in known_source_ids:
            errors.append(f"relation {relation_id} has unknown source_id {row['source_id']}")
        if row["relation"] == "near_confusable_but_distinct" and row["merge_policy"] == "auto_merge":
            errors.append(f"relation {relation_id} cannot auto_merge near_confusable_but_distinct")

        for side_kind_key, side_id_key in (("left_kind", "left_id"), ("right_kind", "right_id")):
            side_kind = row[side_kind_key]
            side_id = row[side_id_key]
            if side_kind == "name" and side_id not in name_ids:
                errors.append(f"relation {relation_id} references unknown name_id {side_id}")
            if side_kind == "form" and side_id not in form_ids:
                errors.append(f"relation {relation_id} references unknown form_id {side_id}")

        if row["left_kind"] == "name":
            name_to_relation_count[row["left_id"]] += 1
        if row["right_kind"] == "name":
            name_to_relation_count[row["right_id"]] += 1

        if row["left_kind"] == "name" and row["right_kind"] == "form":
            form_row = form_by_id.get(row["right_id"])
            if form_row and form_row["name_id"] != row["left_id"]:
                errors.append(f"relation {relation_id} links form {row['right_id']} to wrong name {row['left_id']}")

    for name_id in sorted(name_ids):
        if name_to_relation_count[name_id] == 0:
            errors.append(f"name {name_id} has no relation coverage")

    for row in review_queue:
        if row["subject_kind"] not in VALID_REVIEW_SUBJECT_KINDS:
            errors.append(f"review row {row['review_id']} has invalid subject_kind {row['subject_kind']}")
        if row["suggested_relation"] and row["suggested_relation"] not in VALID_RELATIONS:
            errors.append(
                f"review row {row['review_id']} has invalid suggested_relation {row['suggested_relation']}"
            )
        if row["source_id"] not in known_source_ids:
            errors.append(f"review row {row['review_id']} has unknown source_id {row['source_id']}")

    safe_alias_to_names: dict[str, set[str]] = defaultdict(set)
    alias_ids = {row["alias_id"] for row in aliases}
    if len(alias_ids) != len(aliases):
        errors.append("duplicate alias_id values in aliases.csv")

    for row in aliases:
        alias = row["alias"]
        name_id = row["name_id"]
        if row["form_id"] not in form_ids:
            errors.append(f"alias {row['alias_id']} references unknown form_id {row['form_id']}")
        if name_id not in name_ids:
            errors.append(f"alias {row['alias_id']} references unknown name_id {name_id}")
        if row["merge_policy"] not in VALID_MERGE_POLICIES:
            errors.append(f"alias {row['alias_id']} has invalid merge_policy {row['merge_policy']}")
        if row["source_id"] not in known_source_ids:
            errors.append(f"alias {row['alias_id']} has unknown source_id {row['source_id']}")
        if not _validate_name_like(alias):
            errors.append(f"alias {row['alias_id']} has malformed alias {alias!r}")
        canonical_values = {
            identity_by_id[name_id]["canonical_tt_cyrl"],
            identity_by_id[name_id]["canonical_ru_cyrl"],
            identity_by_id[name_id]["canonical_tt_latn"],
            identity_by_id[name_id]["canonical_ru_latn"],
        }
        if alias in canonical_values:
            errors.append(f"alias {row['alias_id']} duplicates canonical value {alias!r}")
        safe_alias_to_names[normalize.safe(alias)].add(name_id)

    for key, ids in safe_alias_to_names.items():
        if len(ids) > 1:
            errors.append(f"normalized alias {key!r} maps to multiple name_id values: {', '.join(sorted(ids))}")

    return errors


def write_metadata(release_dir: Path) -> None:
    resources = [
        {"name": "identities", "path": "identities.csv", "format": "csv", "schema": {"path": "../../schemas/identities.schema.json"}},
        {"name": "forms", "path": "forms.csv", "format": "csv", "schema": {"path": "../../schemas/forms.schema.json"}},
        {"name": "relations", "path": "relations.csv", "format": "csv", "schema": {"path": "../../schemas/relations.schema.json"}},
        {"name": "review_queue", "path": "review_queue.csv", "format": "csv", "schema": {"path": "../../schemas/review_queue.schema.json"}},
        {"name": "aliases", "path": "aliases.csv", "format": "csv", "schema": {"path": "../../schemas/aliases.schema.json"}},
    ]
    datapackage = {
        "profile": "tabular-data-package",
        "name": "tatar-names",
        "title": "Tatar Names",
        "licenses": [{"name": "CC-BY-4.0", "path": "https://creativecommons.org/licenses/by/4.0/"}],
        "resources": resources,
    }
    (release_dir / "datapackage.json").write_text(json.dumps(datapackage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    croissant = {
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "name": "Tatar Names",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "distribution": [
            {"@type": "DataDownload", "name": "identities", "contentUrl": "data/release/identities.csv", "encodingFormat": "text/csv"},
            {"@type": "DataDownload", "name": "forms", "contentUrl": "data/release/forms.csv", "encodingFormat": "text/csv"},
            {"@type": "DataDownload", "name": "relations", "contentUrl": "data/release/relations.csv", "encodingFormat": "text/csv"},
            {"@type": "DataDownload", "name": "review_queue", "contentUrl": "data/release/review_queue.csv", "encodingFormat": "text/csv"},
            {"@type": "DataDownload", "name": "aliases", "contentUrl": "data/release/aliases.csv", "encodingFormat": "text/csv"},
        ],
    }
    (release_dir / "croissant.json").write_text(json.dumps(croissant, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

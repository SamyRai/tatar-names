from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
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
ALIAS_TYPE_BY_PROFILE = {
    "tt_original": "official_tt",
    "ru_adaptation": "official_ru",
    "tt_cyrl_to_tt_latn_rt2013": "transliteration",
    "ru_cyrl_to_latn_mvd_doc": "passport_latin",
    "common_variant": "common_variant",
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

    for row in excluded:
        source_id = row["source_id"]
        if source_id and source_id not in known_source_ids:
            errors.append(f"excluded entity {row['original_name_id']} has unknown source_id {source_id}")

    return errors


def build_release_rows(source_dir: str | Path | None = None) -> dict[str, list[dict[str, str]]]:
    base = Path(source_dir) if source_dir is not None else default_source_dir()
    entities = source_table(base, "entities")
    attestations = source_table(base, "attestations")

    active_entities = [row for row in entities if row["status"] == "active"]
    entity_ids = {row["entity_id"] for row in active_entities}

    names_rows = [
        {
            "name_id": row["entity_id"],
            "gender": row["gender"],
            "canonical_tt_cyrl": row["canonical_tt_cyrl"],
            "canonical_ru_cyrl": row["canonical_ru_cyrl"],
            "canonical_tt_latn": row["canonical_tt_latn"],
            "canonical_ru_latn": row["canonical_ru_latn"],
            "source_id": row["source_id"],
            "source_row": row["source_row"],
            "status": row["status"],
            "notes": row["entity_type"],
        }
        for row in active_entities
    ]

    candidate_forms = [row for row in attestations if row["entity_id"] in entity_ids]
    exact_to_rows: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in candidate_forms:
        exact_to_rows[(row["form"], row["script"], row["language_tag"])].append(row)

    forms_rows: list[dict[str, str]] = []
    for rows in exact_to_rows.values():
        if len({row["entity_id"] for row in rows}) > 1:
            continue
        row = rows[0]
        forms_rows.append(
            {
                "form_id": row["attestation_id"].replace("at_", "f_"),
                "name_id": row["entity_id"],
                "form": row["form"],
                "script": row["script"],
                "language_tag": row["language_tag"],
                "profile": row["profile"],
                "is_canonical": row["is_canonical"],
                "confidence": row["confidence"],
                "source_id": row["source_id"],
                "evidence_id": row["evidence_id"],
            }
        )
    forms_rows.sort(key=lambda row: row["form_id"])

    alias_candidates: list[dict[str, str]] = []
    for row in forms_rows:
        if row["is_canonical"] == "true":
            continue
        alias_candidates.append(
            {
                "name_id": row["name_id"],
                "alias": row["form"],
                "script": row["script"],
                "language_tag": row["language_tag"],
                "alias_type": ALIAS_TYPE_BY_PROFILE[row["profile"]],
                "method": row["profile"],
                "confidence": row["confidence"],
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
        aliases_rows.append(rows[0])
    aliases_rows.sort(key=lambda row: (row["name_id"], row["alias"], row["method"]))
    for index, row in enumerate(aliases_rows, start=1):
        row["alias_id"] = f"a_{index:07d}"

    return {"names": names_rows, "forms": forms_rows, "aliases": aliases_rows}


def validate_release(data_dir: str | Path | None = None) -> list[str]:
    base = Path(data_dir) if data_dir is not None else default_release_dir()
    errors: list[str] = []
    names = release_table(base, "names")
    forms = release_table(base, "forms")
    aliases = release_table(base, "aliases")
    known_source_ids = bibliography_source_ids(base)

    name_ids = {row["name_id"] for row in names}
    name_by_id = {row["name_id"]: row for row in names}
    if len(name_ids) != len(names):
        errors.append("duplicate name_id values in names.csv")

    canonical_by_id = {row["name_id"]: row["canonical_ru_cyrl"] for row in names}
    for row in names:
        name_id = row["name_id"]
        if row["gender"] not in VALID_GENDERS:
            errors.append(f"{name_id} has invalid gender {row['gender']}")
        if row["status"] not in VALID_STATUSES:
            errors.append(f"{name_id} has invalid status {row['status']}")
        if row["notes"] not in VALID_ENTITY_TYPES:
            errors.append(f"{name_id} has invalid release notes/type {row['notes']}")
        if row["source_id"] not in known_source_ids:
            errors.append(f"{name_id} has unknown source_id {row['source_id']}")
        for field in ("canonical_tt_cyrl", "canonical_ru_cyrl", "canonical_tt_latn", "canonical_ru_latn"):
            if not _validate_name_like(row[field]):
                errors.append(f"{name_id} has malformed {field} {row[field]!r}")
        if detect_generated_formation(row):
            errors.append(f"{name_id} leaked generated formation into release: {row['canonical_tt_cyrl']!r}")

    form_ids = {row["form_id"] for row in forms}
    if len(form_ids) != len(forms):
        errors.append("duplicate form_id values in forms.csv")

    exact_form_to_names: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    canonical_form_ids: set[str] = set()
    for row in forms:
        form = row["form"]
        name_id = row["name_id"]
        if name_id not in name_ids:
            errors.append(f"form {row['form_id']} references unknown name_id {name_id}")
        if row["script"] not in VALID_SCRIPTS:
            errors.append(f"form {row['form_id']} has invalid script {row['script']}")
        if row["profile"] not in VALID_FORM_PROFILES:
            errors.append(f"form {row['form_id']} has invalid profile {row['profile']}")
        if row["source_id"] not in known_source_ids:
            errors.append(f"form {row['form_id']} has unknown source_id {row['source_id']}")
        if row["is_canonical"] not in {"true", "false"}:
            errors.append(f"form {row['form_id']} has invalid is_canonical {row['is_canonical']}")
        if not _validate_name_like(form):
            errors.append(f"form {row['form_id']} has malformed form {form!r}")
        if detect_generated_formation(
            {
                "canonical_tt_cyrl": form if row["language_tag"] == "tt-Cyrl" else "",
                "canonical_ru_cyrl": form if row["language_tag"] == "ru-Cyrl" else "",
                "canonical_tt_latn": form if row["language_tag"] == "tt-Latn" else "",
                "canonical_ru_latn": form if row["language_tag"] == "ru-Latn" else "",
                "gender": name_by_id.get(name_id, {}).get("gender", "unknown"),
            }
        ):
            errors.append(f"form {row['form_id']} leaked generated formation into release: {form!r}")
        exact_form_to_names[(row["form"], row["script"], row["language_tag"])].add(name_id)
        if row["is_canonical"] == "true":
            canonical_form_ids.add(name_id)

    for key, ids in exact_form_to_names.items():
        if len(ids) > 1:
            errors.append(f"exact release form {key!r} maps to multiple names: {', '.join(sorted(ids))}")

    missing_canonical_forms = name_ids - canonical_form_ids
    if missing_canonical_forms:
        errors.append(f"names without canonical forms: {', '.join(sorted(missing_canonical_forms)[:10])}")

    safe_alias_to_names: dict[str, set[str]] = defaultdict(set)
    for row in aliases:
        alias = row["alias"]
        name_id = row["name_id"]
        if name_id not in name_ids:
            errors.append(f"alias {row['alias_id']} references unknown name_id {name_id}")
        if row["source_id"] not in known_source_ids:
            errors.append(f"alias {row['alias_id']} has unknown source_id {row['source_id']}")
        if not _validate_name_like(alias):
            errors.append(f"alias {row['alias_id']} has malformed alias {alias!r}")
        safe_alias_to_names[normalize.safe(alias)].add(name_id)
        if alias in canonical_by_id.values() and canonical_by_id.get(name_id) != alias:
            errors.append(f"alias {row['alias_id']} reintroduces canonical collision for {alias!r}")

    for key, ids in safe_alias_to_names.items():
        if len(ids) > 1:
            errors.append(f"normalized alias {key!r} maps to multiple name_id values: {', '.join(sorted(ids))}")

    return errors


def write_metadata(release_dir: Path) -> None:
    resources = [
        {"name": "names", "path": "names.csv", "format": "csv", "schema": {"path": "../../schemas/names.schema.json"}},
        {"name": "forms", "path": "forms.csv", "format": "csv", "schema": {"path": "../../schemas/forms.schema.json"}},
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
            {"@type": "DataDownload", "name": "names", "contentUrl": "data/release/names.csv", "encodingFormat": "text/csv"},
            {"@type": "DataDownload", "name": "forms", "contentUrl": "data/release/forms.csv", "encodingFormat": "text/csv"},
            {"@type": "DataDownload", "name": "aliases", "contentUrl": "data/release/aliases.csv", "encodingFormat": "text/csv"},
        ],
    }
    (release_dir / "croissant.json").write_text(json.dumps(croissant, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

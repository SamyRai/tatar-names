from __future__ import annotations

import os
import shutil
from pathlib import Path

from tatar_names.data import default_release_dir, default_source_dir
from tatar_names.pipeline import (
    build_release_rows,
    validate_release,
    validate_source,
    write_csv_table,
    write_metadata,
)

RELEASE_TABLES: dict[str, tuple[str, list[str]]] = {
    "identities": (
        "identities.csv",
        [
            "name_id",
            "entity_type",
            "gender",
            "origin_family",
            "usage_community",
            "canonical_tt_cyrl",
            "canonical_ru_cyrl",
            "canonical_tt_latn",
            "canonical_ru_latn",
            "primary_form_global",
            "primary_form_tt",
            "primary_form_ru",
            "source_id",
            "source_row",
            "status",
            "notes",
        ],
    ),
    "forms": (
        "forms.csv",
        [
            "form_id",
            "name_id",
            "form",
            "script",
            "language_tag",
            "form_role",
            "identity_status",
            "profile",
            "confidence",
            "source_id",
            "evidence_id",
            "merge_policy",
        ],
    ),
    "relations": (
        "relations.csv",
        [
            "relation_id",
            "left_kind",
            "left_id",
            "right_kind",
            "right_id",
            "relation",
            "merge_policy",
            "confidence",
            "evidence_type",
            "source_id",
            "evidence_id",
            "notes",
        ],
    ),
    "review_queue": (
        "review_queue.csv",
        [
            "review_id",
            "subject_kind",
            "subject_id",
            "queue_reason",
            "suggested_relation",
            "source_id",
            "evidence_id",
            "notes",
        ],
    ),
    "aliases": (
        "aliases.csv",
        [
            "alias_id",
            "form_id",
            "name_id",
            "alias",
            "script",
            "language_tag",
            "alias_type",
            "method",
            "confidence",
            "merge_policy",
            "source_id",
            "rule_id",
        ],
    ),
}
METADATA_FILES = ("datapackage.json", "croissant.json")
OBSOLETE_RELEASE_FILES = ("names.csv",)


def _write_release_tables(target_dir: Path, rows: dict[str, list[dict[str, str]]]) -> None:
    for table_name, (filename, fieldnames) in RELEASE_TABLES.items():
        write_csv_table(target_dir / filename, rows[table_name], fieldnames)


def main() -> None:
    source_dir = default_source_dir()
    release_dir = default_release_dir()
    # Sibling of the release dir: same filesystem, so promotion is os.replace.
    staging_dir = release_dir.parent / ".release-staging"

    source_errors = validate_source(source_dir)
    if source_errors:
        raise SystemExit("Source validation failed:\n" + "\n".join(f"- {error}" for error in source_errors))

    rows = build_release_rows(source_dir)

    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)
    try:
        _write_release_tables(staging_dir, rows)
        write_metadata(staging_dir)

        release_errors = validate_release(staging_dir)
        if release_errors:
            raise SystemExit("Release validation failed:\n" + "\n".join(f"- {error}" for error in release_errors))

        release_dir.mkdir(parents=True, exist_ok=True)
        for filename in (*(filename for filename, _ in RELEASE_TABLES.values()), *METADATA_FILES):
            os.replace(staging_dir / filename, release_dir / filename)
        for filename in OBSOLETE_RELEASE_FILES:
            path = release_dir / filename
            if path.exists():
                path.unlink()
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
